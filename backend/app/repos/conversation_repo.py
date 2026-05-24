"""ConversationTurnRepo: append-only log of writer/assistant messages, scoped to a branch.

Only this module touches ConversationTurnOrm. It returns Pydantic ConversationTurns,
never ORM objects, so the persistence layer stays hidden from everything downstream.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models_v2 import ConversationTurn
from app.domain.orm_v2 import ConversationTurnOrm


def _to_turn(row: ConversationTurnOrm) -> ConversationTurn:
    return ConversationTurn(
        id=row.id,
        branch_id=row.branch_id,
        role=row.role,
        content=row.content,
        created_at=row.created_at,
    )


class ConversationTurnRepo(ABC):
    @abstractmethod
    async def append_turn(self, *, branch_id: UUID, role: str, content: str) -> ConversationTurn: ...

    @abstractmethod
    async def list_turns(
        self, branch_id: UUID, *, limit: int = 50, before: datetime | None = None,
    ) -> list[ConversationTurn]: ...

    @abstractmethod
    async def get_turn(self, turn_id: UUID) -> ConversationTurn | None: ...


class SqlConversationTurnRepo(ConversationTurnRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_turn(self, *, branch_id: UUID, role: str, content: str) -> ConversationTurn:
        row = ConversationTurnOrm(
            branch_id=branch_id,
            role=role,
            content=content,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_turn(row)

    # Fetch many turns in a branch with the newest first, capped at 50
    # This is used to show chat history
    async def list_turns(
        self, branch_id: UUID, *, limit: int = 50, before: datetime | None = None,
    ) -> list[ConversationTurn]:
        stmt = select(ConversationTurnOrm).where(ConversationTurnOrm.branch_id == branch_id)
        if before is not None:
            stmt = stmt.where(ConversationTurnOrm.created_at < before)
        stmt = stmt.order_by(ConversationTurnOrm.created_at.desc()).limit(limit)

        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_turn(r) for r in rows]

    # Fetch a turn by id
    async def get_turn(self, turn_id: UUID) -> ConversationTurn | None:
        stmt = select(ConversationTurnOrm).where(ConversationTurnOrm.id == turn_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_turn(row) if row is not None else None
