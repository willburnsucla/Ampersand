"""VonnegutFramework: arc-shape classification plus arc-level pacing anomalies.

Wraps classify_arc and detect_arc_anomalies from narrative.py.
"""
from __future__ import annotations

from app.domain.models_v2 import Beat
from app.domain.narrative import classify_arc, detect_arc_anomalies
from app.frameworks.base import Framework, FrameworkResult


class VonnegutFramework(Framework):
    name = "vonnegut"

    def analyze(self, beats: list[Beat]) -> FrameworkResult:
        return FrameworkResult(
            framework=self.name,
            arc=classify_arc(beats),
            anomalies=tuple(detect_arc_anomalies(beats)),
        )
