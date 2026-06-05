"""ConversationTurnRepo: append-only log of writer/assistant messages, scoped to a branch.

Only this module touches ConversationTurnOrm. It returns Pydantic ConversationTurns,
never ORM objects, so the persistence layer stays hidden from everything downstream.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
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


class InMemoryConversationTurnRepo(ConversationTurnRepo):
    """In-memory v2 ConversationTurnRepo for mock mode.

    Distinct from the v1 InMemoryConversationRepo below: this one satisfies the v2
    ConversationTurnRepo abc (keyword append_turn, newest-first list_turns) and is
    what dependencies_v2 wires in mock mode. created_at is tz-aware to mirror the
    timestamptz column so a before cursor compares cleanly.
    """

    def __init__(self) -> None:
        self._turns: dict[UUID, ConversationTurn] = {}

    async def append_turn(self, *, branch_id: UUID, role: str, content: str) -> ConversationTurn:
        turn = ConversationTurn(
            branch_id=branch_id,
            role=role,
            content=content,
            created_at=datetime.now(UTC),
        )
        self._turns[turn.id] = turn
        return turn.model_copy(deep=True)

    async def list_turns(
        self, branch_id: UUID, *, limit: int = 50, before: datetime | None = None,
    ) -> list[ConversationTurn]:
        rows = [
            t
            for t in self._turns.values()
            if t.branch_id == branch_id and (before is None or t.created_at < before)
        ]
        # newest first, then cap at limit
        rows = list(reversed(rows))[:limit]
        return [t.model_copy(deep=True) for t in rows]

    async def get_turn(self, turn_id: UUID) -> ConversationTurn | None:
        row = self._turns.get(turn_id)
        return row.model_copy(deep=True) if row is not None else None


class InMemoryConversationRepo:
    """Mock implementation for dev-mock mode — no DB needed."""

    def __init__(self) -> None:
        self._turns: list[ConversationTurn] = []

    async def append_turn(self, turn) -> None:  # type: ignore[override]
        self._turns.append(turn)

    async def list_turns(self, branch_id: UUID, *, limit: int = 50, before=None):
        return [t for t in self._turns if t.branch_id == branch_id][-limit:]

    async def get_turn(self, turn_id: UUID):
        return next((t for t in self._turns if t.id == turn_id), None)


# Alias that router.py expects
ConversationRepo = InMemoryConversationRepo
