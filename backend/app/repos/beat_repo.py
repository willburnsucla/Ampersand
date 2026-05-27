"""BeatRepo: CRUD on beats, scoped to a branch.

Only this module touches BeatOrm. It returns Pydantic Beats, never ORM
objects, so the persistence layer stays hidden from everything downstream.

sequence_index_in_branch is caller supplied. the schema enforces a unique
constraint on (branch_id, sequence_index_in_branch), so two concurrent appends
that both read max+1 will collide and the loser surfaces as IntegrityError.
for MVP that bubbles to the caller, retry is the callers job. an atomic
upsert or a SELECT FOR UPDATE on the branch would make this race free, deferred
until we see real contention in practice.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models_v2 import Beat
from app.domain.orm_v2 import BeatOrm


# DB -> APP helper
def _to_beat(row: BeatOrm) -> Beat:
    return Beat(
        id=row.id,
        branch_id=row.branch_id,
        sequence_index_in_branch=row.sequence_index_in_branch,
        logline=row.logline,
        content=row.content,
        turning_point=row.turning_point,
        valence=row.valence,
        arousal=row.arousal,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

class BeatRepo(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        branch_id: UUID,
        sequence_index_in_branch: int,
        logline: str,
        content: dict | None = None,
        turning_point: str | None = None,
        valence: float | None = None,
        arousal: float | None = None,
    ) -> Beat: ...

    @abstractmethod
    async def get(self, beat_id: UUID, *, branch_id: UUID) -> Beat | None: ...

    @abstractmethod
    async def list(self, *, branch_id: UUID) -> list[Beat]: ...

    @abstractmethod
    async def set_status(self, beat_id: UUID, status: str, *, branch_id: UUID) -> Beat: ...

class SqlBeatRepo(BeatRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        branch_id: UUID,
        sequence_index_in_branch: int,
        logline: str,
        content: dict | None = None,
        turning_point: str | None = None,
        valence: float | None = None,
        arousal: float | None = None,
    ) -> Beat:
        row = BeatOrm(
            branch_id=branch_id,
            sequence_index_in_branch=sequence_index_in_branch,
            logline=logline,
            content=content if content is not None else {},
            turning_point=turning_point,
            valence=valence,
            arousal=arousal,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_beat(row)

    async def get(self, beat_id: UUID, *, branch_id: UUID) -> Beat | None:
        stmt = select(BeatOrm).where(
            BeatOrm.id == beat_id,
            BeatOrm.branch_id == branch_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_beat(row) if row is not None else None

    async def list(self, *, branch_id: UUID) -> list[Beat]:
        stmt = (
            select(BeatOrm)
            .where(BeatOrm.branch_id == branch_id)
            .order_by(BeatOrm.sequence_index_in_branch)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_beat(r) for r in rows]

    async def set_status(self, beat_id: UUID, status: str, *, branch_id: UUID) -> Beat:
        stmt = select(BeatOrm).where(
            BeatOrm.id == beat_id,
            BeatOrm.branch_id == branch_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"beat {beat_id} not found in this branch")
        row.status = status
        await self._session.flush()
        await self._session.refresh(row)
        return _to_beat(row)