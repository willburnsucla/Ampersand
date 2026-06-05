"""Extractor v2: prose to a proposed beat.

MockExtractorV2 is deterministic with no external calls. GeminiExtractorV2 does real
extraction over the Gemini API. Both sit behind the ExtractorV2 abc; the orchestrator
depends on the abc, never a concrete extractor.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.core.config import settings
from app.domain.models_v2 import (
    Beat,
    Character,
    ConversationTurn,
    Setting,
    Theme,
    TurningPoint,
)


class LlmContextV2(BaseModel):
    """Everything the extractor sees for one turn. Built by ContextBuilder."""

    project_id: UUID
    branch_id: UUID
    user_message: str
    recent_turns: list[ConversationTurn] = Field(default_factory=list)
    recent_beats: list[Beat] = Field(default_factory=list)
    characters: list[Character] = Field(default_factory=list)
    themes: list[Theme] = Field(default_factory=list)
    settings: list[Setting] = Field(default_factory=list)


class ProposedBeat(BaseModel):
    """A beat the extractor wants to add, before it is written or sequenced.

    Entities are named, not id'd. The DeltaApplier resolves the names against
    existing project entities and creates the ones that dont exist.
    """

    logline: str
    content: dict[str, Any] = Field(default_factory=dict)
    turning_point: TurningPoint | None = None
    valence: float | None = Field(default=None, ge=0, le=1)
    arousal: float | None = Field(default=None, ge=0, le=1)
    character_names: list[str] = Field(default_factory=list)
    theme_names: list[str] = Field(default_factory=list)
    setting_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _affect_is_atomic(self) -> ProposedBeat:
        if (self.valence is None) != (self.arousal is None):
            raise ValueError("valence and arousal must both be set or both omitted")
        return self


class ExtractionResultV2(BaseModel):
    reply: str
    proposed_beat: ProposedBeat | None = None


class ExtractorV2(ABC):
    @abstractmethod
    async def extract(self, ctx: LlmContextV2) -> ExtractionResultV2: ...


# keyword to entity name, the deterministic stand-in for real extraction
_CHARACTERS = {"detective": "Maya", "wizard": "Alaric",
               "knight": "Sir Gawain", "queen": "Eleanor"}
_SETTINGS = {"forest": "The Dark Forest", "castle": "The Keep",
             "harbor": "Old Harbor", "ship": "The Marlow"}
_THEMES = {"justice": "Justice", "betrayal": "Betrayal",
           "love": "Love", "revenge": "Revenge"}


def _matches(text: str, table: dict[str, str]) -> list[str]:
    return [name for kw, name in table.items() if kw in text]


class MockExtractorV2(ExtractorV2):
    """Deterministic extractor for dev and tests.

    The logline is the writer's message trimmed to one line; entities come from a
    fixed keyword table, so the same message always yields the same beat.
    """

    async def extract(self, ctx: LlmContextV2) -> ExtractionResultV2:
        text = ctx.user_message.strip()
        lowered = text.lower()
        logline = text.splitlines()[0][:200] if text else "Untitled beat"

        proposed = ProposedBeat(
            logline=logline,
            character_names=_matches(lowered, _CHARACTERS),
            theme_names=_matches(lowered, _THEMES),
            setting_names=_matches(lowered, _SETTINGS),
        )
        reply = f'Drafted a beat from that: "{logline}". Want to keep it?'
        return ExtractionResultV2(reply=reply, proposed_beat=proposed)


# ── Gemini ────────────────────────────────────────────────────────────────────

_DEGRADE_REPLY = "I couldn't shape that into a beat. Tell me a bit more about what happens?"


class _GeminiBeatArgs(BaseModel):
    """Structured-output schema handed to Gemini: a ProposedBeat plus a reply. Omits the
    free-form content dict, which Gemini's response schema does not model well; the
    DeltaApplier fills content in later.
    """

    reply: str
    logline: str
    turning_point: TurningPoint | None = None
    valence: float | None = Field(default=None, ge=0, le=1)
    arousal: float | None = Field(default=None, ge=0, le=1)
    character_names: list[str] = Field(default_factory=list)
    theme_names: list[str] = Field(default_factory=list)
    setting_names: list[str] = Field(default_factory=list)


def _system_prompt(ctx: LlmContextV2) -> str:
    # name existing entities and recent beats so the model reuses names the DeltaApplier
    # can resolve, instead of inventing near-duplicates.
    def names(items) -> str:
        return ", ".join(i.name for i in items) or "none yet"

    recent = " / ".join(b.logline for b in ctx.recent_beats[-5:]) or "none yet"
    return (
        "You turn a writer's prose into exactly one structured story beat. Reuse these "
        "existing names when they fit, and score valence and arousal together (both in "
        "0..1) or leave both unset.\n"
        f"Characters: {names(ctx.characters)}\n"
        f"Themes: {names(ctx.themes)}\n"
        f"Settings: {names(ctx.settings)}\n"
        f"Recent beats: {recent}"
    )


def _parse_beat(args: dict[str, Any]) -> ExtractionResultV2 | None:
    # pull the reply, validate the rest as a ProposedBeat. a malformed or out-of-range
    # beat raises and returns None, which the caller turns into an escalation.
    reply = args.pop("reply", "")
    try:
        proposed = ProposedBeat.model_validate(args)
    except ValidationError:
        return None
    return ExtractionResultV2(reply=reply or "Drafted a beat from that.", proposed_beat=proposed)


class GeminiExtractorV2(ExtractorV2):
    """Real extraction over Gemini (native google-genai), behind the same ExtractorV2 abc.

    Asks for structured json matching _GeminiBeatArgs, parses it into a ProposedBeat, tries
    a fast model and escalates once to a stronger one if the first reply has no usable beat
    (no json, or a beat that fails validation such as a half-set or out-of-range affect
    pair). If both fail it returns a reply with no beat, so a bad turn degrades instead of
    500ing. Only content failures degrade; an api error (network, auth, quota) propagates.

    The google-genai sdk is imported only in this module. The client is injectable so tests
    run with no network.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        model: str | None = None,
        escalation_model: str | None = None,
    ) -> None:
        self._client = client or genai.Client(api_key=settings.gemini_api_key)
        self._model = model or settings.gemini_model
        self._escalation_model = (
            escalation_model or settings.gemini_escalation_model or self._model
        )

    async def extract(self, ctx: LlmContextV2) -> ExtractionResultV2:
        system = _system_prompt(ctx)
        for model in (self._model, self._escalation_model):
            result = await self._extract_once(model, system, ctx.user_message)
            if result is not None:
                return result
        return ExtractionResultV2(reply=_DEGRADE_REPLY, proposed_beat=None)

    async def _extract_once(
        self, model: str, system: str, user_message: str
    ) -> ExtractionResultV2 | None:
        response = await self._client.aio.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=_GeminiBeatArgs,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            return None
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        return _parse_beat(data)
