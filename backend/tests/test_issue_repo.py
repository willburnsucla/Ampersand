"""Integration tests for SqlIssueRepo against a real Postgres (testcontainers)."""
import uuid

import pytest

from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.issue_repo import SqlIssueRepo

async def _make_branch(db_session, *, owner_id: str = "user-1") -> BranchOrm:
    project = ProjectOrm(owner_id=owner_id, title="test project")
    db_session.add(project)
    await db_session.flush()

    branch = BranchOrm(project_id=project.id, name="main")
    db_session.add(branch)
    await db_session.flush()
    return branch

# tests for create / get / list
async def test_create_then_get_returns_it(db_session):
    branch = await _make_branch(db_session)
    repo = SqlIssueRepo(db_session)

    beat_a, beat_b = uuid.uuid4(), uuid.uuid4()

    created = await repo.create(
        branch_id=branch.id,
        type="contradiction",
        description="Sarah was in Boston in beat 3 but New York in beat 5",
        related_beat_ids=[beat_a, beat_b],
    )

    assert created.type == "contradiction"
    assert created.status == "open"
    assert created.related_beat_ids == [beat_a, beat_b]
    assert created.related_entity_ids == []
    assert created.resolved_at is None
    assert created.id is not None

# Shouldn't be able to read across branches
async def test_get_with_wrong_branch_returns_none(db_session):
    branch_a = await _make_branch(db_session)
    branch_b = await _make_branch(db_session)
    repo = SqlIssueRepo(db_session)

    issue = await repo.create(branch_id=branch_a.id, type="pacing_anomaly", description="...")
    assert await repo.get(issue.id, branch_id=branch_b.id) is None

# Missing id is None
async def test_get_nonexistent_returns_none(db_session):
    branch = await _make_branch(db_session)
    repo = SqlIssueRepo(db_session)
    assert await repo.get(uuid.uuid4(), branch_id=branch.id) is None

# list() is properly scoped per branch
async def test_list_scopes_to_branch(db_session):
    branch_a = await _make_branch(db_session)
    branch_b = await _make_branch(db_session)
    repo = SqlIssueRepo(db_session)

    await repo.create(branch_id=branch_a.id, type="contradiction", description="A1")
    await repo.create(branch_id=branch_a.id, type="timeline_gap", description="A2")
    await repo.create(branch_id=branch_b.id, type="contradiction", description="B1")

    a = await repo.list(branch_id=branch_a.id)
    assert {i.description for i in a} == {"A1", "A2"}

# test set_status
async def test_set_status_progresses_lifecycle(db_session):
    branch = await _make_branch(db_session)
    repo = SqlIssueRepo(db_session)
