"""Unit tests for the framework wrappers and registry. Pure, no DB.

The arc/anomaly math itself is covered by test_narrative.py; these tests pin the
framework wrappers (uniform analyze surface, arc only where it applies) and the
registry's name to instance lookup.
"""
import uuid

import pytest
from pydantic import ValidationError

from app.domain.models_v2 import Beat
from app.frameworks import (
    DEFAULT_REGISTRY,
    FrameworkRegistry,
    PapalampidiFramework,
    VonnegutFramework,
)


def _beat(seq: int, *, valence: float | None = None, tp: str | None = None) -> Beat:
    return Beat(
        branch_id=uuid.uuid4(),
        sequence_index_in_branch=seq,
        logline=f"beat {seq}",
        valence=valence,
        turning_point=tp,
    )


def _man_in_hole() -> list[Beat]:
    # high start, low crisis, high end -> man_in_hole
    return [
        _beat(0, valence=0.8, tp="tp1"),
        _beat(1, valence=0.6),
        _beat(2, valence=0.5, tp="tp3"),
        _beat(3, valence=0.1, tp="tp4"),
        _beat(4, valence=0.8, tp="tp5"),
    ]


# Vonnegut classifies the arc and stamps its own name on the result
def test_vonnegut_classifies_arc_and_sets_name():
    result = VonnegutFramework().analyze(_man_in_hole())
    assert result.framework == "vonnegut"
    assert result.arc == "man_in_hole"


# Papalampidi scores turning points, never an arc shape
def test_papalampidi_never_returns_an_arc():
    result = PapalampidiFramework().analyze(_man_in_hole())
    assert result.framework == "papalampidi"
    assert result.arc is None


# a strictly rising branch is the canonical LLM-pacing smell Vonnegut flags
def test_vonnegut_flags_monotonic_valence():
    rising = [_beat(i, valence=0.1 * i) for i in range(6)]
    result = VonnegutFramework().analyze(rising)
    assert any(a.kind == "arc" for a in result.anomalies)


# the result DTO is frozen, so a caller cannot mutate analysis after the fact
def test_framework_result_is_frozen():
    result = VonnegutFramework().analyze(_man_in_hole())
    with pytest.raises(ValidationError):
        result.arc = "icarus"  # type: ignore[misc]


# the registry resolves each name to the matching concrete strategy
def test_registry_get_returns_the_named_framework():
    assert isinstance(DEFAULT_REGISTRY.get("vonnegut"), VonnegutFramework)
    assert isinstance(DEFAULT_REGISTRY.get("papalampidi"), PapalampidiFramework)


# an unknown framework name is a hard error, not a silent None
def test_registry_unknown_name_raises():
    with pytest.raises(ValueError):
        DEFAULT_REGISTRY.get("aristotle")


# the registry enumerates exactly the registered frameworks, in one place
def test_registry_lists_all_frameworks():
    assert DEFAULT_REGISTRY.names() == ["papalampidi", "vonnegut"]
    assert len(DEFAULT_REGISTRY.all()) == 2


# an empty registry still answers queries without blowing up
def test_empty_registry_is_well_defined():
    empty = FrameworkRegistry([])
    assert empty.names() == []
    assert empty.all() == []
    with pytest.raises(ValueError):
        empty.get("vonnegut")
