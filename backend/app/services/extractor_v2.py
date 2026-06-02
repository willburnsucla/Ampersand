"""Extractor v2: prose to a proposed beat. Mock impl for dev and tests.

MockExtractorV2 is deterministic with no external calls. A ClaudeExtractorV2 goes
behind the same ExtractorV2 abc later; the orchestrator depends on the abc, never
a concrete extractor.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

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
    valence: float | None = None
    arousal: float | None = None
    character_names: list[str] = Field(default_factory=list)
    theme_names: list[str] = Field(default_factory=list)
    setting_names: list[str] = Field(default_factory=list)


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
