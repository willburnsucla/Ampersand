"""ConsistencyChecker: turns branch analysis into Issues.

ABC plus one heuristic impl. The heuristic does the cheap structural checks it
can make without reading prose; the semantic checks (contradiction, character
drift, world-rule violations) are the job of an LLM-backed impl swapped in
behind the same ABC later, with no change to the catalog or orchestrator above
it.

Both methods return un-persisted Issue DTOs. Deciding which to write through
IssueRepo is the caller's job; the checker only analyzes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.domain.models_v2 import Beat, Issue, IssueType
from app.frameworks import DEFAULT_REGISTRY, FrameworkRegistry
from app.repos.beat_repo import BeatRepo


class ConsistencyChecker(ABC):
    @abstractmethod
    async def inline_check(self, beat: Beat, context_beats: list[Beat]) -> list[Issue]:
        """Flag issues a single just-written beat raises against its neighbors."""
        ...

    @abstractmethod
    async def deep_scan(self, branch_id: UUID) -> list[Issue]:
        """Scan a whole branch and return every issue found."""
        ...


def _issue(
    branch_id: UUID,
    type_: IssueType,
    description: str,
    beats: Sequence[UUID] = (),
) -> Issue:
    return Issue(
        branch_id=branch_id,
        type=type_,
        description=description,
        related_beat_ids=list(beats),
    )


class HeuristicConsistencyChecker(ConsistencyChecker):
    """Structural-only checker: cheap, deterministic, no prose understanding.

    inline_check flags timeline gaps and turning points tagged without a valence.
    deep_scan composes the framework registry for pacing anomalies and adds a
    branch-wide timeline-gap pass.
    """

    def __init__(
        self, beats: BeatRepo, frameworks: FrameworkRegistry = DEFAULT_REGISTRY
    ) -> None:
        self._beats = beats
        self._frameworks = frameworks

    async def inline_check(self, beat: Beat, context_beats: list[Beat]) -> list[Issue]:
        issues: list[Issue] = []

        prior = [
            b.sequence_index_in_branch
            for b in context_beats
            if b.sequence_index_in_branch < beat.sequence_index_in_branch
        ]
        if prior and beat.sequence_index_in_branch > max(prior) + 1:
            missing = beat.sequence_index_in_branch - max(prior) - 1
            issues.append(_issue(
                beat.branch_id, "timeline_gap",
                f"Beat at sequence {beat.sequence_index_in_branch} skips {missing} "
                f"index(es) after {max(prior)}; a beat may be missing.",
                (beat.id,),
            ))

        if beat.turning_point is not None and (beat.valence is None or beat.arousal is None):
            issues.append(_issue(
                beat.branch_id, "framework_misuse",
                f"Beat is tagged {beat.turning_point.upper()} but has no affect scored; "
                "arc classification needs both valence and arousal at turning points.",
                (beat.id,),
            ))

        return issues

    async def deep_scan(self, branch_id: UUID) -> list[Issue]:
        beats = await self._beats.list(branch_id=branch_id)
        issues: list[Issue] = []

        for framework in self._frameworks.all():
            for anomaly in framework.analyze(beats).anomalies:
                issues.append(_issue(
                    branch_id, "pacing_anomaly",
                    anomaly.message, anomaly.related_beat_ids,
                ))

        issues.extend(self._timeline_gaps(branch_id, beats))
        return issues

    @staticmethod
    def _timeline_gaps(branch_id: UUID, beats: list[Beat]) -> list[Issue]:
        ordered = sorted(beats, key=lambda b: b.sequence_index_in_branch)
        out: list[Issue] = []
        for prev, curr in zip(ordered, ordered[1:], strict=False):
            gap = curr.sequence_index_in_branch - prev.sequence_index_in_branch
            if gap > 1:
                out.append(_issue(
                    branch_id, "timeline_gap",
                    f"Sequence jumps from {prev.sequence_index_in_branch} to "
                    f"{curr.sequence_index_in_branch}; {gap - 1} index(es) missing.",
                    (prev.id, curr.id),
                ))
        return out
