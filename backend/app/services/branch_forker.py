"""BranchForker: create an alternate branch that inherits the story up to a beat.

create_fork on the repo only records the new branch and its fork point; this service also
copies the parent's beats up to and including that point into the new branch, so the
alternate starts as the same story and diverges from there.
"""
from __future__ import annotations

from uuid import UUID

from app.domain.models_v2 import Branch
from app.repos.beat_repo import BeatRepo
from app.repos.branch_repo import BranchRepo


class BranchForker:
    def __init__(self, *, branches: BranchRepo, beats: BeatRepo) -> None:
        self._branches = branches
        self._beats = beats

    async def fork(
        self,
        *,
        project_id: UUID,
        parent_branch_id: UUID,
        from_beat_id: UUID,
        name: str | None = None,
    ) -> Branch:
        """Fork parent_branch_id at from_beat_id, carrying the story up to that beat.

        Raises ValueError if the beat is not in the parent branch, or if the fork beat
        already has its three alternates (the repo's per-beat cap).
        """
        fork_beat = await self._beats.get(from_beat_id, branch_id=parent_branch_id)
        if fork_beat is None:
            raise ValueError(f"beat {from_beat_id} is not in branch {parent_branch_id}")

        branch = await self._branches.create_fork(
            project_id=project_id,
            parent_branch_id=parent_branch_id,
            created_from_beat_id=from_beat_id,
            name=name,
        )

        # carry the story up to and including the fork point, in order, so the alternate
        # begins as the same beats and diverges from here
        for beat in await self._beats.list(branch_id=parent_branch_id):
            if beat.sequence_index_in_branch <= fork_beat.sequence_index_in_branch:
                await self._beats.create(
                    branch_id=branch.id,
                    sequence_index_in_branch=beat.sequence_index_in_branch,
                    logline=beat.logline,
                    content=beat.content,
                    turning_point=beat.turning_point,
                    valence=beat.valence,
                    arousal=beat.arousal,
                )
        return branch
