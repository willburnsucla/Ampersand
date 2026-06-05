"""ProjectRepo: CRUD on projects, scoped to an owner.

Only this module touches ProjectOrm. It returns Pydantic Projects, never ORM
objects, so the persistence layer stays hidden from everything downstream.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models_v2 import Project
from app.domain.orm_v2 import ProjectOrm


def _to_project(row: ProjectOrm) -> Project:
    return Project(
        id=row.id,
        owner_id=row.owner_id,
        title=row.title,
        primary_branch_id=row.primary_branch_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ProjectRepo(ABC):
    @abstractmethod
    async def create(self, *, title: str, owner_id: str) -> Project: ...

    @abstractmethod
    async def get(self, project_id: UUID, *, owner_id: str) -> Project | None: ...

    @abstractmethod
    async def list(self, *, owner_id: str) -> list[Project]: ...

    @abstractmethod
    async def set_primary_branch(self, project_id: UUID, branch_id: UUID, *, owner_id: str) -> Project: ...

    @abstractmethod
    async def delete(self, project_id: UUID, *, owner_id: str) -> bool: ...


class SqlProjectRepo(ProjectRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, title: str, owner_id: str) -> Project:
        row = ProjectOrm(owner_id=owner_id, title=title)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_project(row)

    async def get(self, project_id: UUID, *, owner_id: str) -> Project | None:
        stmt = select(ProjectOrm).where(
            ProjectOrm.id == project_id,
            ProjectOrm.owner_id == owner_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_project(row) if row is not None else None

    async def list(self, *, owner_id: str) -> list[Project]:
        stmt = (
            select(ProjectOrm)
            .where(ProjectOrm.owner_id == owner_id)
            .order_by(ProjectOrm.updated_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_project(r) for r in rows]

    async def set_primary_branch(self, project_id: UUID, branch_id: UUID, *, owner_id: str) -> Project:
        stmt = select(ProjectOrm).where(
            ProjectOrm.id == project_id,
            ProjectOrm.owner_id == owner_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"project {project_id} not found for this owner")
        row.primary_branch_id = branch_id
        await self._session.flush()
        await self._session.refresh(row)
        return _to_project(row)

    async def delete(self, project_id: UUID, *, owner_id: str) -> bool:
        stmt = sql_delete(ProjectOrm).where(
            ProjectOrm.id == project_id,
            ProjectOrm.owner_id == owner_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class InMemoryProjectRepo(ProjectRepo):
    """In-memory ProjectRepo for mock mode. Stores Pydantic Projects keyed by id."""

    def __init__(self) -> None:
        self._projects: dict[UUID, Project] = {}

    async def create(self, *, title: str, owner_id: str) -> Project:
        project = Project(owner_id=owner_id, title=title)
        self._projects[project.id] = project
        return project.model_copy(deep=True)

    async def get(self, project_id: UUID, *, owner_id: str) -> Project | None:
        row = self._projects.get(project_id)
        if row is None or row.owner_id != owner_id:
            return None
        return row.model_copy(deep=True)

    async def list(self, *, owner_id: str) -> list[Project]:
        rows = [p for p in self._projects.values() if p.owner_id == owner_id]
        # sql orders by updated_at desc; reversed insertion is the in-memory stand-in
        return [p.model_copy(deep=True) for p in reversed(rows)]

    async def set_primary_branch(
        self, project_id: UUID, branch_id: UUID, *, owner_id: str
    ) -> Project:
        row = self._projects.get(project_id)
        if row is None or row.owner_id != owner_id:
            raise ValueError(f"project {project_id} not found for this owner")
        row.primary_branch_id = branch_id
        return row.model_copy(deep=True)

    async def delete(self, project_id: UUID, *, owner_id: str) -> bool:
        row = self._projects.get(project_id)
        if row is None or row.owner_id != owner_id:
            return False
        del self._projects[project_id]
        return True
