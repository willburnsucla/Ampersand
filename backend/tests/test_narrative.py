"""Narrative analysis tests. Covers the Tian et al. 2024 bias signals."""
from __future__ import annotations

import uuid

from app.domain.models_v2 import Beat, TurningPoint
from app.domain.narrative import (
    classify_arc,
    detect_arc_anomalies,
    detect_tp_anomalies,
)

_BRANCH_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _beat(seq: int, *, valence: float | None = None, tp: TurningPoint | None = None) -> Beat:
    return Beat(
        branch_id=_BRANCH_ID,
        sequence_index_in_branch=seq,
        logline=f"beat {seq}",
        valence=valence,
        arousal=valence,
        turning_point=tp,
    )


# ── classify_arc ──────────────────────────────────────────────────────────────

def test_classify_arc_requires_tp1_tp4_tp5():
    beats = [_beat(0, valence=0.5, tp="tp1"), _beat(5, valence=0.5)]
    assert classify_arc(beats) is None


def test_classify_arc_returns_none_without_valence_at_anchors():
    beats = [
        _beat(0, tp="tp1"),
        _beat(5, valence=0.5, tp="tp4"),
        _beat(9, valence=0.7, tp="tp5"),
    ]
    assert classify_arc(beats) is None


def test_classify_arc_recognizes_man_in_hole():
    beats = [
        _beat(0, valence=0.7, tp="tp1"),
        _beat(1, valence=0.5),
        _beat(2, valence=0.4),
        _beat(3, valence=0.2, tp="tp4"),
        _beat(4, valence=0.5),
        _beat(5, valence=0.7, tp="tp5"),
    ]
    assert classify_arc(beats) == "man_in_hole"


def test_classify_arc_recognizes_icarus():
    beats = [
        _beat(0, valence=0.3, tp="tp1"),
        _beat(1, valence=0.6),
        _beat(2, valence=0.8, tp="tp4"),
        _beat(3, valence=0.4),
        _beat(4, valence=0.2, tp="tp5"),
    ]
    assert classify_arc(beats) == "icarus"


def test_classify_arc_recognizes_rags_to_riches():
    beats = [
        _beat(0, valence=0.2, tp="tp1"),
        _beat(1, valence=0.4),
        _beat(2, valence=0.5, tp="tp4"),
        _beat(3, valence=0.7),
        _beat(4, valence=0.9, tp="tp5"),
    ]
    assert classify_arc(beats) == "rags_to_riches"


def test_classify_arc_recognizes_riches_to_rags():
    beats = [
        _beat(0, valence=0.9, tp="tp1"),
        _beat(1, valence=0.7),
        _beat(2, valence=0.5, tp="tp4"),
        _beat(3, valence=0.3),
        _beat(4, valence=0.1, tp="tp5"),
    ]
    assert classify_arc(beats) == "riches_to_rags"


def test_classify_arc_recognizes_cinderella():
    # TP3 dips below start; ends much higher → cinderella, not rags_to_riches
    beats = [
        _beat(0, valence=0.5, tp="tp1"),
        _beat(1, valence=0.3),
        _beat(2, valence=0.2, tp="tp3"),
        _beat(3, valence=0.4, tp="tp4"),
        _beat(4, valence=0.8, tp="tp5"),
    ]
    assert classify_arc(beats) == "cinderella"


def test_classify_arc_recognizes_oedipus():
    # TP3 peaks above start; ends much lower → oedipus, not riches_to_rags
    beats = [
        _beat(0, valence=0.5, tp="tp1"),
        _beat(1, valence=0.7),
        _beat(2, valence=0.8, tp="tp3"),
        _beat(3, valence=0.5, tp="tp4"),
        _beat(4, valence=0.2, tp="tp5"),
    ]
    assert classify_arc(beats) == "oedipus"


# ── detect_arc_anomalies ──────────────────────────────────────────────────────

def test_monotonically_positive_valence_is_flagged():
    beats = [_beat(i, valence=0.3 + i * 0.1) for i in range(6)]
    messages = [a.message for a in detect_arc_anomalies(beats)]
    assert any("monotonic" in m.lower() for m in messages)


def test_swinging_valence_is_not_flagged_for_monotony():
    beats = [_beat(i, valence=v) for i, v in enumerate([0.5, 0.7, 0.3, 0.6, 0.2, 0.8])]
    messages = [a.message for a in detect_arc_anomalies(beats)]
    assert not any("monotonic" in m.lower() for m in messages)


def test_flat_second_half_is_flagged():
    beats = [_beat(i, valence=v) for i, v in enumerate([0.2, 0.4, 0.8, 0.5, 0.5, 0.5, 0.5])]
    messages = [a.message for a in detect_arc_anomalies(beats)]
    assert any("flat" in m.lower() for m in messages)


def test_too_few_scored_beats_returns_no_arc_anomalies():
    assert detect_arc_anomalies([_beat(i, valence=0.5) for i in range(3)]) == []


# ── detect_tp_anomalies ───────────────────────────────────────────────────────

def test_climax_too_early_is_flagged():
    beats = [_beat(i) for i in range(10)]
    beats[4] = _beat(4, tp="tp5")
    messages = [a.message for a in detect_tp_anomalies(beats)]
    assert any("TP5" in m and "earlier" in m for m in messages)


def test_climax_at_expected_position_is_not_flagged_as_early():
    beats = [_beat(i) for i in range(10)]
    beats[8] = _beat(8, tp="tp5")
    messages = [a.message for a in detect_tp_anomalies(beats)]
    assert not any("TP5" in m and "earlier" in m for m in messages)


def test_missing_tp4_in_long_branch_is_flagged():
    beats = [_beat(i) for i in range(10)]
    messages = [a.message for a in detect_tp_anomalies(beats)]
    assert any("TP4" in m for m in messages)


def test_short_branch_does_not_flag_missing_tp4():
    beats = [_beat(i) for i in range(4)]
    messages = [a.message for a in detect_tp_anomalies(beats)]
    assert not any("TP4" in m for m in messages)


def test_out_of_order_turning_points_are_flagged():
    beats = [
        _beat(0, tp="tp2"),
        _beat(1, tp="tp1"),
    ]
    messages = [a.message for a in detect_tp_anomalies(beats)]
    assert any("before an earlier" in m for m in messages)


def test_in_order_turning_points_pass():
    beats = [
        _beat(0, tp="tp1"),
        _beat(2, tp="tp2"),
        _beat(5, tp="tp3"),
    ]
    messages = [a.message for a in detect_tp_anomalies(beats)]
    assert not any("before an earlier" in m for m in messages)
