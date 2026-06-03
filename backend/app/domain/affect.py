"""Pair-passing helper for services. Beat itself exposes valence/arousal as flat fields."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Affect(BaseModel):
    model_config = ConfigDict(frozen=True)

    valence: float = Field(ge=0, le=1)
    arousal: float = Field(ge=0, le=1)
