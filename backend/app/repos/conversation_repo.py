"""
ConversationRepo — T-003. Append-only log of conversation turns.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from app.domain.models import ConversationTurn


class ConversationRepo(ABC):
    @abstractmethod
    async def append_turn(self, turn: ConversationTurn) -> ConversationTurn: ...

    @abstractmethod
    async def list_turns(
        self,
        branch_id: UUID,
        *,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[ConversationTurn]:
        """Return turns for branch_id, newest-first, up to limit. Optionally before a cursor."""

    @abstractmethod
    async def get_turn(self, turn_id: UUID) -> ConversationTurn | None: ...


class InMemoryConversationRepo(ConversationRepo):
    def __init__(self) -> None:
        self._turns: list[ConversationTurn] = []

    async def append_turn(self, turn: ConversationTurn) -> ConversationTurn:
        self._turns.append(deepcopy(turn))
        return deepcopy(turn)

    async def list_turns(
        self,
        branch_id: UUID,
        *,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[ConversationTurn]:
        turns = [t for t in self._turns if t.branch_id == branch_id]
        if before is not None:
            turns = [t for t in turns if t.created_at < before]
        # newest first
        turns.sort(key=lambda t: t.created_at, reverse=True)
        return [deepcopy(t) for t in turns[:limit]]

    async def get_turn(self, turn_id: UUID) -> ConversationTurn | None:
        for turn in self._turns:
            if turn.id == turn_id:
                return deepcopy(turn)
        return None

    def reset(self) -> None:
        self._turns.clear()


class PostgresConversationRepo(ConversationRepo):
    async def append_turn(self, turn: ConversationTurn) -> ConversationTurn:
        raise NotImplementedError

    async def list_turns(
        self,
        branch_id: UUID,
        *,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[ConversationTurn]:
        raise NotImplementedError

    async def get_turn(self, turn_id: UUID) -> ConversationTurn | None:
        raise NotImplementedError
