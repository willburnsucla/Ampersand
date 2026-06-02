"""Unit tests for HeuristicConsistencyChecker. Pure: a fake BeatRepo, no DB.

The checker's logic is the unit under test, so deep_scan runs against an
in-memory fake repo rather than testcontainers, which keeps it fast and isolated.
"""
import uuid

from app.domain.models_v2 import Beat
from app.services.consistency_checker import HeuristicConsistencyChecker

BRANCH = uuid.uuid4()


def _beat(seq: int, *, valence: float | None = None, tp: str | None = None) -> Beat:
    return Beat(
        branch_id=BRANCH,
        sequence_index_in_branch=seq,
        logline=f"beat {seq}",
        valence=valence,
        turning_point=tp,
    )


class _FakeBeatRepo:
    """Just enough BeatRepo for deep_scan: list() over a preset branch."""

    def __init__(self, beats: list[Beat]) -> None:
        self._beats = beats

    async def list(self, *, branch_id):
        return [b for b in self._beats if b.branch_id == branch_id]


def _checker(beats: list[Beat] | None = None) -> HeuristicConsistencyChecker:
    return HeuristicConsistencyChecker(_FakeBeatRepo(beats or []))


# a contiguous, well-formed beat raises nothing
async def test_inline_check_clean_beat_is_silent():
    context = [_beat(0), _beat(1)]
    issues = await _checker().inline_check(_beat(2), context)
    assert issues == []


# a jump in sequence index surfaces a timeline_gap
async def test_inline_check_flags_timeline_gap():
    context = [_beat(0), _beat(1), _beat(2)]
    issues = await _checker().inline_check(_beat(5), context)
    assert [i.type for i in issues] == ["timeline_gap"]
    assert issues[0].branch_id == BRANCH


# a turning point tagged without valence is a framework_misuse
async def test_inline_check_flags_tp_without_valence():
    issues = await _checker().inline_check(_beat(1, tp="tp4"), [_beat(0)])
    assert [i.type for i in issues] == ["framework_misuse"]


# a tagged turning point WITH valence is fine
async def test_inline_check_tp_with_valence_is_silent():
    issues = await _checker().inline_check(_beat(1, tp="tp4", valence=0.2), [_beat(0)])
    assert issues == []


# both structural problems on one beat surface as two distinct issues
async def test_inline_check_reports_both_problems():
    context = [_beat(0), _beat(1)]
    issues = await _checker().inline_check(_beat(4, tp="tp4"), context)
    assert {i.type for i in issues} == {"timeline_gap", "framework_misuse"}


# deep_scan composes the frameworks: a monotonic branch yields a pacing_anomaly
async def test_deep_scan_surfaces_pacing_anomaly():
    rising = [_beat(i, valence=0.1 * i) for i in range(6)]
    issues = await _checker(rising).deep_scan(BRANCH)
    assert any(i.type == "pacing_anomaly" for i in issues)
    assert all(i.branch_id == BRANCH for i in issues)


# deep_scan flags a branch-wide sequence gap
async def test_deep_scan_flags_branch_timeline_gap():
    gapped = [_beat(0), _beat(1), _beat(4)]
    issues = await _checker(gapped).deep_scan(BRANCH)
    assert any(i.type == "timeline_gap" for i in issues)


# an empty branch scans clean
async def test_deep_scan_empty_branch_is_silent():
    assert await _checker([]).deep_scan(BRANCH) == []
