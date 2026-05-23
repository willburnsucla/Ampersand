"""BranchRepo: CRUD + state transitions on branches, scoped to a project.

Only this module touches BranchOrm. Returns Pydantic Branches, never ORM objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.branch_state_machine import BranchEvent, BranchStateMachine
from app.domain.models_v2 import Branch
from app.domain.orm_v2 import BranchOrm


def _to_branch(row: BranchOrm) -> Branch:
    return Branch(
        id=row.id,
        project_id=row.project_id,
        parent_branch_id=row.parent_branch_id,
        created_from_beat_id=row.created_from_beat_id,
        name=row.name,
        state=row.state,
        declared_arc=row.declared_arc,
        created_at=row.created_at,
    )

class BranchRepo(ABC):
    @abstractmethod
    async def create(
        self, 
        *,
        project_id: UUID,
        name: str | None = None,
        parent_branch_id: UUID | None = None,
        created_from_beat_id: UUID | None = None,
        declared_arc: str | None = None,
    ) -> Branch: ...

    @abstractmethod
    async def get(self, branch_id: UUID, *, project_id: UUID) -> Branch | None: ...

    @abstractmethod
    async def list(self, *, project_id: UUID) -> list[Branch]: ...

    @abstractmethod
    async def transition(self, branch_id: UUID, event: BranchEvent, *, project_id: UUID) -> Branch: ...
    
class SqlBranchRepo(BranchRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str | None = None,
        parent_branch_id: UUID | None = None,
        created_from_beat_id: UUID | None = None,
        declared_arc: str | None = None,
    ) -> Branch:
        row = BranchOrm(
            project_id=project_id,
            name=name,
            parent_branch_id=parent_branch_id,
            created_from_beat_id=created_from_beat_id,
            declared_arc=declared_arc,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_branch(row)

    async def get(self, branch_id: UUID, *, project_id: UUID) -> Branch | None:
        stmt = select(BranchOrm).where(
            BranchOrm.id == branch_id,
            BranchOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_branch(row) if row is not None else None

    async def list(self, *, project_id: UUID) -> list[Branch]:
        stmt = (
            select(BranchOrm)
            .where(BranchOrm.project_id == project_id)
            .order_by(BranchOrm.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_branch(r) for r in rows]

    async def transition(self, branch_id: UUID, event: BranchEvent, *, project_id: UUID) -> Branch:
        stmt = select(BranchOrm).where(
            BranchOrm.id == branch_id,
            BranchOrm.project_id == project_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"branch {branch_id} not found in this project")
        # next_state raises InvalidTransitionError if illegal let it propagate
        # note transition doesn't validate the transition itself, but rather delegates that to BranchStateMachine
        row.state = BranchStateMachine.next_state(row.state, event)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_branch(row)