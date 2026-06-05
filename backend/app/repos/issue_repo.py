"""IssueRepo: CRUD + lifecycle on issues, scoped to a branch.

Only this module touches IssueOrm. Returns Pydantic Issues, never ORM objects.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models_v2 import Issue
from app.domain.orm_v2 import IssueOrm


def _to_issue(row: IssueOrm) -> Issue:
    return Issue(
        id=row.id,
        branch_id=row.branch_id,
        type=row.type,
        description=row.description,
        related_beat_ids=list(row.related_beat_ids),
        related_entity_ids=list(row.related_entity_ids),
        status=row.status,
        detected_at=row.detected_at,
        resolved_at=row.resolved_at,
    )


class IssueRepo(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        branch_id: UUID,
        type: str,
        description: str,
        related_beat_ids: list[UUID] | None = None,
        related_entity_ids: list[UUID] | None = None,
    ) -> Issue: ...

    @abstractmethod
    async def get(self, issue_id: UUID, *, branch_id: UUID) -> Issue | None: ...

    @abstractmethod
    async def list(self, *, branch_id: UUID) -> list[Issue]: ...

    @abstractmethod
    async def set_status(self, issue_id: UUID, status: str, *, branch_id: UUID) -> Issue: ...


class SqlIssueRepo(IssueRepo):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        branch_id: UUID,
        type: str,
        description: str,
        related_beat_ids: list[UUID] | None = None,
        related_entity_ids: list[UUID] | None = None,
    ) -> Issue:
        row = IssueOrm(
            branch_id=branch_id,
            type=type,
            description=description,
            related_beat_ids=related_beat_ids if related_beat_ids is not None else [],
            related_entity_ids=related_entity_ids if related_entity_ids is not None else [],
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_issue(row)

    async def get(self, issue_id: UUID, *, branch_id: UUID) -> Issue | None:
        stmt = select(IssueOrm).where(
            IssueOrm.id == issue_id,
            IssueOrm.branch_id == branch_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_issue(row) if row is not None else None

    async def list(self, *, branch_id: UUID) -> list[Issue]:
        stmt = (
            select(IssueOrm)
            .where(IssueOrm.branch_id == branch_id)
            .order_by(IssueOrm.detected_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_issue(r) for r in rows]

    async def set_status(self, issue_id: UUID, status: str, *, branch_id: UUID) -> Issue:
        stmt = select(IssueOrm).where(
            IssueOrm.id == issue_id,
            IssueOrm.branch_id == branch_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise ValueError(f"issue {issue_id} not found in this branch")

        row.status = status
        if status == "resolved":
            row.resolved_at = datetime.utcnow()

        await self._session.flush()
        await self._session.refresh(row)
        return _to_issue(row)


class InMemoryIssueRepo(IssueRepo):
    """In-memory IssueRepo for mock mode."""

    def __init__(self) -> None:
        self._issues: dict[UUID, Issue] = {}

    async def create(
        self,
        *,
        branch_id: UUID,
        type: str,
        description: str,
        related_beat_ids: list[UUID] | None = None,
        related_entity_ids: list[UUID] | None = None,
    ) -> Issue:
        issue = Issue(
            branch_id=branch_id,
            type=type,
            description=description,
            related_beat_ids=related_beat_ids if related_beat_ids is not None else [],
            related_entity_ids=related_entity_ids if related_entity_ids is not None else [],
        )
        self._issues[issue.id] = issue
        return issue.model_copy(deep=True)

    async def get(self, issue_id: UUID, *, branch_id: UUID) -> Issue | None:
        row = self._issues.get(issue_id)
        if row is None or row.branch_id != branch_id:
            return None
        return row.model_copy(deep=True)

    async def list(self, *, branch_id: UUID) -> list[Issue]:
        rows = [i for i in self._issues.values() if i.branch_id == branch_id]
        # sql orders by detected_at desc; reversed insertion is the in-memory stand-in
        return [i.model_copy(deep=True) for i in reversed(rows)]

    async def set_status(self, issue_id: UUID, status: str, *, branch_id: UUID) -> Issue:
        row = self._issues.get(issue_id)
        if row is None or row.branch_id != branch_id:
            raise ValueError(f"issue {issue_id} not found in this branch")
        row.status = status
        if status == "resolved":
            row.resolved_at = datetime.now(UTC)
        return row.model_copy(deep=True)
