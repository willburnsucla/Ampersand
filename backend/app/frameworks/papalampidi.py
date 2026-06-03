"""PapalampidiFramework: turning-point pacing and ordering anomalies.

Wraps detect_tp_anomalies from narrative.py. Scores turning-point structure,
not arc shape, so its result always leaves arc None.
"""
from __future__ import annotations

from app.domain.models_v2 import Beat
from app.domain.narrative import detect_tp_anomalies
from app.frameworks.base import Framework, FrameworkResult


class PapalampidiFramework(Framework):
    name = "papalampidi"

    def analyze(self, beats: list[Beat]) -> FrameworkResult:
        return FrameworkResult(
            framework=self.name,
            arc=None,
            anomalies=tuple(detect_tp_anomalies(beats)),
        )
