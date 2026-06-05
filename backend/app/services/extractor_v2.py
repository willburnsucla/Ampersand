"""Extractor v2: prose to proposed beats.

MockExtractorV2 is deterministic with no external calls (one beat per non-empty line).
GeminiExtractorV2 does real extraction over the Gemini API and can break a passage into
several beats. Both sit behind the ExtractorV2 abc; the orchestrator depends on the abc,
never a concrete extractor.
"""
from __future__ import annotations

import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)

# transient gemini errors worth retrying before giving up (high-demand 503s, rate-limit
# 429s); a spike usually clears within a second or two.
_TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 4
_RETRY_BASE_SECONDS = 1.0


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
    proposed_beats: list[ProposedBeat] = Field(default_factory=list)


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

    One beat per non-empty line of the message, so a multi-line passage becomes several
    beats. Entities come from a fixed keyword table, so the same message always yields the
    same beats.
    """

    async def extract(self, ctx: LlmContextV2) -> ExtractionResultV2:
        lines = [ln.strip() for ln in ctx.user_message.splitlines() if ln.strip()]
        if not lines:
            lines = ["Untitled beat"]
        beats = [
            ProposedBeat(
                logline=line[:200],
                character_names=_matches(line.lower(), _CHARACTERS),
                theme_names=_matches(line.lower(), _THEMES),
                setting_names=_matches(line.lower(), _SETTINGS),
            )
            for line in lines
        ]
        plural = "s" if len(beats) != 1 else ""
        reply = f"Drafted {len(beats)} beat{plural} from that."
        return ExtractionResultV2(reply=reply, proposed_beats=beats)


# ── Gemini ────────────────────────────────────────────────────────────────────

_DEGRADE_REPLY = "I couldn't shape that into a beat. Tell me a bit more about what happens?"


class _GeminiBeat(BaseModel):
    """One beat in Gemini's structured output. No content dict (Gemini's response schema
    does not model a free-form object well; the DeltaApplier fills content in later)."""

    logline: str
    turning_point: TurningPoint | None = None
    valence: float | None = Field(default=None, ge=0, le=1)
    arousal: float | None = Field(default=None, ge=0, le=1)
    character_names: list[str] = Field(default_factory=list)
    theme_names: list[str] = Field(default_factory=list)
    setting_names: list[str] = Field(default_factory=list)


class _GeminiExtraction(BaseModel):
    """The whole structured response: the beats in order, plus one reply to the writer."""

    reply: str
    beats: list[_GeminiBeat] = Field(default_factory=list)


def _system_prompt(ctx: LlmContextV2) -> str:
    # name existing entities and recent beats so the model reuses names the DeltaApplier
    # can resolve, instead of inventing near-duplicates.
    def names(items) -> str:
        return ", ".join(i.name for i in items) or "none yet"

    existing = " / ".join(b.logline for b in ctx.recent_beats) or "none yet"
    return (
        "You are an expert story editor whose only job is to ORGANIZE a writer's prose "
        "into the beats it already contains. You are curatorial, not advisory: you "
        "structure and label what the writer actually wrote. You never invent plot, add "
        "characters, settings, or events that are not in their text, embellish, or change "
        "their meaning, and you never suggest what should happen next or judge the work.\n"
        "Break the passage into the distinct story beats it contains, in the order they "
        "happen. A short line is usually one beat; a long passage is several, one per "
        "distinct moment. For each beat write a one-sentence logline drawn from the "
        "writer's own content, and tag the characters, themes, and settings it involves, "
        "reusing the existing names below when they fit. Where the prose makes the "
        "emotional tone clear, score valence and arousal together (both 0..1); otherwise "
        "leave both unset rather than guessing.\n"
        "Do NOT repeat a beat that is already in the story below, even if you would word "
        "it differently: return only genuinely new beats, and an empty beats list if the "
        "passage adds nothing new.\n"
        "Your reply to the writer is one short, neutral sentence about what you organized "
        "(how many beats you added, or that nothing was new). Do not praise, critique, or "
        "advise.\n"
        f"Characters: {names(ctx.characters)}\n"
        f"Themes: {names(ctx.themes)}\n"
        f"Settings: {names(ctx.settings)}\n"
        f"Beats already in the story: {existing}"
    )


class GeminiExtractorV2(ExtractorV2):
    """Real extraction over Gemini (native google-genai), behind the same ExtractorV2 abc.

    Asks gemini for structured json (a reply plus a list of beats), validates each beat
    into a ProposedBeat and keeps the good ones. Tries a fast model and escalates once to
    a stronger one if it gets nothing usable; if both fail it returns a reply with no
    beats, so a bad turn degrades instead of 500ing. Only content failures degrade; an api
    error (network, auth, quota) propagates.

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
        return ExtractionResultV2(reply=_DEGRADE_REPLY, proposed_beats=[])

    async def _generate(self, model: str, system: str, user_message: str):
        """Call gemini, retrying transient high-demand errors with a short backoff.

        A non-transient error (auth, bad request) raises at once; a transient 503/429 is
        retried a few times, then raised so the caller's fallback can take over.
        """
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=_GeminiExtraction,
        )
        last_exc: genai.errors.APIError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await self._client.aio.models.generate_content(
                    model=model, contents=user_message, config=config
                )
            except genai.errors.APIError as exc:
                if getattr(exc, "code", None) not in _TRANSIENT_STATUS:
                    raise
                last_exc = exc
                logger.warning(
                    "gemini %s on attempt %d/%d",
                    getattr(exc, "code", "?"), attempt + 1, _MAX_ATTEMPTS,
                )
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_RETRY_BASE_SECONDS * 2**attempt)
        raise last_exc  # every attempt hit a transient error

    async def _extract_once(
        self, model: str, system: str, user_message: str
    ) -> ExtractionResultV2 | None:
        response = await self._generate(model, system, user_message)
        text = getattr(response, "text", None)
        if not text:
            return None
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

        raw_beats = data.get("beats", [])
        beats: list[ProposedBeat] = []
        for raw in raw_beats:
            try:
                beats.append(ProposedBeat.model_validate(raw))
            except ValidationError:
                continue  # drop one malformed beat, keep the rest of the passage
        if raw_beats and not beats:
            return None  # the model offered beats but all were malformed; escalate
        # an intentionally empty list (the passage only repeats beats already in the story)
        # is a valid, successful result: zero new beats, not a failure to escalate.
        reply = data.get("reply") or f"Drafted {len(beats)} beats."
        return ExtractionResultV2(reply=reply, proposed_beats=beats)


class FallbackExtractorV2(ExtractorV2):
    """Runs a primary extractor, dropping to a fallback if the primary raises.

    Keeps a turn producing beats when the real model is unavailable (e.g. a sustained
    gemini outage): any error from the primary routes to the fallback instead of failing
    the turn.
    """

    def __init__(self, *, primary: ExtractorV2, fallback: ExtractorV2) -> None:
        self._primary = primary
        self._fallback = fallback

    async def extract(self, ctx: LlmContextV2) -> ExtractionResultV2:
        try:
            return await self._primary.extract(ctx)
        except Exception:
            logger.warning("primary extractor failed, using fallback", exc_info=True)
            return await self._fallback.extract(ctx)
