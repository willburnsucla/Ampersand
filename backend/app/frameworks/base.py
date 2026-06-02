"""Framework: an interchangeable narrative lens over a branch of beats.

Each framework wraps the pure functions in narrative.py behind one analyze()
surface, so the catalog and the consistency checker treat every framework the
same way and adding a third is a new file plus a registry line. Vonnegut
classifies arc shape; Papalampidi scores turning points.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.domain.models_v2 import Beat, VonnegutArc
from app.domain.narrative import Anomaly


class FrameworkResult(BaseModel):
    """What a framework returns: an optional arc label plus any anomalies.

    arc is set only by frameworks that classify arc shape; turning-point
    frameworks leave it None and report through anomalies.
    """
    model_config = ConfigDict(frozen=True)

    framework: str
    arc: VonnegutArc | None = None
    anomalies: tuple[Anomaly, ...] = ()


class Framework(ABC):
    """One interchangeable narrative-analysis algorithm."""

    name: ClassVar[str]

    @abstractmethod
    def analyze(self, beats: list[Beat]) -> FrameworkResult:
        """Classify the arc (if this framework does) and flag its anomalies."""
        ...
