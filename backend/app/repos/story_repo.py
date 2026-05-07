"""
StoryRepo — T-003. CRUD on stories scoped to a user.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from app.domain.models import Branch, CreateStoryInput, Story


class StoryRepo(ABC):
    @abstractmethod
    async def create(self, input: CreateStoryInput, *, owner_id: str) -> Story: ...

    @abstractmethod
    async def get(self, story_id: UUID, *, owner_id: str) -> Story | None: ...

    @abstractmethod
    async def list(self, *, owner_id: str) -> list[Story]: ...

    @abstractmethod
    async def set_active_branch(self, story_id: UUID, branch_id: UUID) -> None: ...


class InMemoryStoryRepo(StoryRepo):
    def __init__(self) -> None:
        self._stories: dict[UUID, Story] = {}

    async def create(self, input: CreateStoryInput, *, owner_id: str) -> Story:
        story = Story(
            id=uuid.uuid4(),
            owner_id=owner_id,
            title=input.title,
            created_at=datetime.utcnow(),
        )
        self._stories[story.id] = story
        return deepcopy(story)

    async def get(self, story_id: UUID, *, owner_id: str) -> Story | None:
        story = self._stories.get(story_id)
        if story and story.owner_id == owner_id:
            return deepcopy(story)
        return None

    async def list(self, *, owner_id: str) -> list[Story]:
        return [deepcopy(s) for s in self._stories.values() if s.owner_id == owner_id]

    async def set_active_branch(self, story_id: UUID, branch_id: UUID) -> None:
        if story_id in self._stories:
            self._stories[story_id].active_branch_id = branch_id

    def reset(self) -> None:
        self._stories.clear()


class PostgresStoryRepo(StoryRepo):
    async def create(self, input: CreateStoryInput, *, owner_id: str) -> Story:
        raise NotImplementedError

    async def get(self, story_id: UUID, *, owner_id: str) -> Story | None:
        raise NotImplementedError

    async def list(self, *, owner_id: str) -> list[Story]:
        raise NotImplementedError

    async def set_active_branch(self, story_id: UUID, branch_id: UUID) -> None:
        raise NotImplementedError
