"""
BranchRepo — T-003. CRUD + state transitions for branches.
Delegates state machine validation to BranchStateMachine.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from app.domain.branch_state_machine import BranchEvent, BranchStateMachine
from app.domain.models import Branch, CreateBranchInput


class BranchRepo(ABC):
    @abstractmethod
    async def create(self, input: CreateBranchInput) -> Branch: ...

    @abstractmethod
    async def get(self, branch_id: UUID) -> Branch | None: ...

    @abstractmethod
    async def list(self, *, story_id: UUID) -> list[Branch]: ...

    @abstractmethod
    async def transition(self, branch_id: UUID, event: BranchEvent) -> Branch:
        """Apply a state transition. Raises InvalidTransitionError if disallowed."""


class InMemoryBranchRepo(BranchRepo):
    def __init__(self) -> None:
        self._branches: dict[UUID, Branch] = {}

    async def create(self, input: CreateBranchInput) -> Branch:
        branch = Branch(
            id=uuid.uuid4(),
            story_id=input.story_id,
            parent_branch_id=input.parent_branch_id,
            state="active",
            created_from_beat_id=input.created_from_beat_id,
            name=input.name,
            created_at=datetime.utcnow(),
        )
        self._branches[branch.id] = branch
        return deepcopy(branch)

    async def get(self, branch_id: UUID) -> Branch | None:
        branch = self._branches.get(branch_id)
        return deepcopy(branch) if branch else None

    async def list(self, *, story_id: UUID) -> list[Branch]:
        return [deepcopy(b) for b in self._branches.values() if b.story_id == story_id]

    async def transition(self, branch_id: UUID, event: BranchEvent) -> Branch:
        branch = self._branches.get(branch_id)
        if branch is None:
            raise KeyError(f"Branch {branch_id} not found")
        # Raises InvalidTransitionError if disallowed
        new_state = BranchStateMachine.next_state(branch.state, event)
        branch.state = new_state  # type: ignore[assignment]
        return deepcopy(branch)

    def reset(self) -> None:
        self._branches.clear()


class PostgresBranchRepo(BranchRepo):
    async def create(self, input: CreateBranchInput) -> Branch:
        raise NotImplementedError

    async def get(self, branch_id: UUID) -> Branch | None:
        raise NotImplementedError

    async def list(self, *, story_id: UUID) -> list[Branch]:
        raise NotImplementedError

    async def transition(self, branch_id: UUID, event: BranchEvent) -> Branch:
        raise NotImplementedError
