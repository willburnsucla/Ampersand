"""Integration tests for SqlConversationTurnRepo against a real Postgres (testcontainers)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.orm_v2 import BranchOrm, ConversationTurnOrm, ProjectOrm
from app.repos.conversation_repo import SqlConversationTurnRepo


async def _make_branch(db_session, *, owner_id: str = "user-1") -> BranchOrm:
    project = ProjectOrm(owner_id=owner_id, title="test project")
    db_session.add(project)
    await db_session.flush()

    branch = BranchOrm(project_id=project.id, name="main")
    db_session.add(branch)
    await db_session.flush()
    return branch


# add a writer message then fetch it by id and confirm structure
async def test_append_then_get_returns_it(db_session):
    branch = await _make_branch(db_session)
    repo = SqlConversationTurnRepo(db_session)

    created = await repo.append_turn(
        branch_id=branch.id,
        role="writer",
        content="Sarah finds a body at the pier",
    )

    assert created.role == "writer"
    assert created.content == "Sarah finds a body at the pier"
    assert created.id is not None
    assert created.created_at is not None

    fetched = await repo.get_turn(created.id)
    assert fetched is not None
    assert fetched.id == created.id


# fail on non-existent id
async def test_get_nonexistent_returns_none(db_session):
    repo = SqlConversationTurnRepo(db_session)
    assert await repo.get_turn(uuid.uuid4()) is None


# list is scoped properly
async def test_list_scopes_to_branch(db_session):
    branch_a = await _make_branch(db_session)
    branch_b = await _make_branch(db_session)
    repo = SqlConversationTurnRepo(db_session)

    await repo.append_turn(branch_id=branch_a.id, role="writer", content="A1")
    await repo.append_turn(branch_id=branch_a.id, role="assistant", content="A2")
    await repo.append_turn(branch_id=branch_b.id, role="writer", content="B1")

    a = await repo.list_turns(branch_a.id)
    assert {t.content for t in a} == {"A1", "A2"}


# manually insert older/newer w/timestemps and confirm list returns properly
async def test_list_orders_newest_first(db_session):
    branch = await _make_branch(db_session)

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    oldest = ConversationTurnOrm(
        branch_id=branch.id, role="writer", content="oldest",
        created_at=base - timedelta(hours=1),
    )
    older = ConversationTurnOrm(
        branch_id=branch.id, role="writer", content="older", created_at=base,
    )
    newer = ConversationTurnOrm(
        branch_id=branch.id, role="writer", content="newer",
        created_at=base + timedelta(hours=1),
    )
    db_session.add_all([oldest, older, newer])
    await db_session.flush()

    repo = SqlConversationTurnRepo(db_session)
    turns = await repo.list_turns(branch.id)
    assert [t.content for t in turns] == ["newer", "older", "oldest"]



# limit caps how many we return
async def test_list_respects_limit(db_session):
    branch = await _make_branch(db_session)
    repo = SqlConversationTurnRepo(db_session)

    for i in range(5):
        await repo.append_turn(branch_id=branch.id, role="writer", content=f"msg{i}")

    turns = await repo.list_turns(branch.id, limit=3)
    assert len(turns) == 3


# before cursor excludes anything at or after the cursor. Nice!
async def test_list_before_cursor(db_session):
    branch = await _make_branch(db_session)

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old = ConversationTurnOrm(
        branch_id=branch.id, role="writer", content="old", created_at=base,
    )
    mid = ConversationTurnOrm(
        branch_id=branch.id, role="writer", content="mid",
        created_at=base + timedelta(hours=1),
    )
    new = ConversationTurnOrm(
        branch_id=branch.id, role="writer", content="new",
        created_at=base + timedelta(hours=2),
    )
    db_session.add_all([old, mid, new])
    await db_session.flush()

    repo = SqlConversationTurnRepo(db_session)
    cursor = base + timedelta(hours=1, minutes=30) 
    turns = await repo.list_turns(branch.id, before=cursor)
    assert {t.content for t in turns} == {"mid", "old"}
