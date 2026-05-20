"""Arc classification and pacing-anomaly detection over a branch of beats.

The arc taxonomy (VonnegutArc) and turning-point labels (TurningPoint) live
in models_v2 — this module is just the functions that use them.
"""
from __future__ import annotations

from statistics import mean
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.models_v2 import Beat, TurningPoint, VonnegutArc


# Approximate human-writing positions from Papalampidi et al. 2019.
# Guidance for the "too early" check, not constraints.
_EXPECTED_TP_POSITIONS: dict[TurningPoint, float] = {
    "tp1": 0.10,
    "tp2": 0.30,
    "tp3": 0.55,
    "tp4": 0.75,
    "tp5": 0.90,
}
_TP_TOLERANCE = 0.15
_TP_ORDER: tuple[TurningPoint, ...] = ("tp1", "tp2", "tp3", "tp4", "tp5")


class Anomaly(BaseModel):
    """An observation from narrative analysis. May be persisted as an Issue."""
    model_config = ConfigDict(frozen=True)

    kind: Literal["arc", "turning_point"]
    message: str
    related_beat_ids: tuple[UUID, ...] = ()


# ── Arc classification ────────────────────────────────────────────────────────

def classify_arc(beats: list[Beat]) -> VonnegutArc | None:
    """Best-fit arc shape from the valence at the major turning points.

    Needs TP1, TP4, TP5 tagged with valence. TP3 (if also tagged) lets us
    distinguish cinderella from rags_to_riches and oedipus from riches_to_rags.
    Returns None on ambiguous shapes — never guesses.
    """
    sorted_beats = sorted(beats, key=lambda b: b.sequence_index_in_branch)
    tps = {b.turning_point: b for b in sorted_beats if b.turning_point is not None}

    if not {"tp1", "tp4", "tp5"}.issubset(tps.keys()):
        return None

    start = tps["tp1"].valence
    crisis = tps["tp4"].valence
    end = tps["tp5"].valence
    if start is None or crisis is None or end is None:
        return None

    if crisis < min(start, end) - 0.1:
        return "man_in_hole"
    if crisis > max(start, end) + 0.1:
        return "icarus"

    net = end - start
    midpoint_v = tps["tp3"].valence if "tp3" in tps else None

    if net > 0.2:
        if midpoint_v is not None and midpoint_v < start - 0.1:
            return "cinderella"
        return "rags_to_riches"
    if net < -0.2:
        if midpoint_v is not None and midpoint_v > start + 0.1:
            return "oedipus"
        return "riches_to_rags"

    return None


# ── Anomaly detection ─────────────────────────────────────────────────────────

def detect_arc_anomalies(beats: list[Beat]) -> list[Anomaly]:
    """Flag macro-level pacing issues — monotonic valence + flat second half."""
    scored = [b for b in beats if b.valence is not None]
    if len(scored) < 4:
        return []

    out: list[Anomaly] = []

    deltas = [scored[i + 1].valence - scored[i].valence for i in range(len(scored) - 1)]
    if all(d >= 0 for d in deltas):
        out.append(Anomaly(
            kind="arc",
            message=(
                "Valence rises monotonically across the branch — common in "
                "LLM-generated stories. Consider a setback to add tension."
            ),
            related_beat_ids=tuple(b.id for b in scored),
        ))

    midpoint = len(scored) // 2
    second_half = [b.valence for b in scored[midpoint:]]
    if len(second_half) >= 3 and _stdev(second_half) < 0.05:
        out.append(Anomaly(
            kind="arc",
            message="Second-half valence is flat — emotional stakes may be plateauing.",
            related_beat_ids=tuple(b.id for b in scored[midpoint:]),
        ))

    return out


def detect_tp_anomalies(beats: list[Beat]) -> list[Anomaly]:
    """Flag turning-point pacing and ordering issues."""
    if not beats:
        return []

    sorted_beats = sorted(beats, key=lambda b: b.sequence_index_in_branch)
    tagged = {b.turning_point: b for b in sorted_beats if b.turning_point}
    total = len(sorted_beats)
    out: list[Anomaly] = []

    for tp in ("tp4", "tp5"):
        beat = tagged.get(tp)
        if beat is None:
            continue
        position = sorted_beats.index(beat) / max(total - 1, 1)
        expected = _EXPECTED_TP_POSITIONS[tp]
        if position < expected - _TP_TOLERANCE:
            out.append(Anomaly(
                kind="turning_point",
                message=(
                    f"{tp.upper()} arrives at {position:.0%} through the branch — "
                    f"earlier than typical (~{expected:.0%}). Pacing may feel rushed."
                ),
                related_beat_ids=(beat.id,),
            ))

    if total >= 8 and "tp4" not in tagged:
        out.append(Anomaly(
            kind="turning_point",
            message="No Major Setback (TP4) tagged yet — consider where the story turns.",
        ))

    tp_to_position = {b.turning_point: i for i, b in enumerate(sorted_beats) if b.turning_point}
    seen = -1
    for tp in _TP_ORDER:
        if tp not in tp_to_position:
            continue
        if tp_to_position[tp] < seen:
            out.append(Anomaly(
                kind="turning_point",
                message=f"{tp.upper()} appears before an earlier turning point in the sequence.",
                related_beat_ids=(sorted_beats[tp_to_position[tp]].id,),
            ))
        seen = max(seen, tp_to_position[tp])

    return out


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return (sum((v - avg) ** 2 for v in values) / (len(values) - 1)) ** 0.5
