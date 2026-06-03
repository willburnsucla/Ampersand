"""Integration tests for SqlProjectRepo against a real Postgres (testcontainers)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.project_repo import SqlProjectRepo


async def test_create_then_get_returns_it(db_session):
    repo = SqlProjectRepo(db_session)
    created = await repo.create(title="My Story", owner_id="user-1")

    assert created.title == "My Story"
    assert created.owner_id == "user-1"
    assert created.primary_branch_id is None
    assert created.created_at is not None

    fetched = await repo.get(created.id, owner_id="user-1")
    assert fetched is not None
    assert fetched.id == created.id


async def test_get_with_wrong_owner_returns_none(db_session):
    repo = SqlProjectRepo(db_session)
    created = await repo.create(title="Mine", owner_id="user-1")

    assert await repo.get(created.id, owner_id="someone-else") is None


async def test_get_nonexistent_returns_none(db_session):
    repo = SqlProjectRepo(db_session)
    assert await repo.get(uuid.uuid4(), owner_id="user-1") is None


async def test_list_scopes_to_owner(db_session):
    repo = SqlProjectRepo(db_session)
    await repo.create(title="A", owner_id="user-1")
    await repo.create(title="B", owner_id="user-1")
    await repo.create(title="C", owner_id="user-2")

    mine = await repo.list(owner_id="user-1")
    assert {p.title for p in mine} == {"A", "B"}


async def test_list_orders_newest_first(db_session):
    # postgres now() is constant within a txn, so set explicit timestamps
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    older = ProjectOrm(owner_id="user-1", title="older", created_at=base, updated_at=base)
    newer = ProjectOrm(
        owner_id="user-1", title="newer",
        created_at=base, updated_at=base + timedelta(hours=1),
    )
    db_session.add_all([older, newer])
    await db_session.flush()

    repo = SqlProjectRepo(db_session)
    listed = await repo.list(owner_id="user-1")
    assert [p.title for p in listed] == ["newer", "older"]


async def test_set_primary_branch(db_session):
    repo = SqlProjectRepo(db_session)
    project = await repo.create(title="X", owner_id="user-1")

    # need a real branch for the FK to hold
    branch = BranchOrm(project_id=project.id, name="main")
    db_session.add(branch)
    await db_session.flush()

    updated = await repo.set_primary_branch(project.id, branch.id, owner_id="user-1")
    assert updated.primary_branch_id == branch.id


async def test_set_primary_branch_wrong_owner_raises(db_session):
    repo = SqlProjectRepo(db_session)
    project = await repo.create(title="X", owner_id="user-1")

    with pytest.raises(ValueError):
        await repo.set_primary_branch(project.id, uuid.uuid4(), owner_id="not-the-owner")
