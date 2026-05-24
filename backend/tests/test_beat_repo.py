"""Integration tests for SqlBeatRepo against a real Postgres (testcontainers)."""
import uuid

import pytest

from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.beat_repo import SqlBeatRepo


# Branch helper for our beats
# BeatOrm makes use of a FK s.t. a beat must belong to an existing branch, otherwise Postgres rejects AND a branch must bleong to an existing project
async def _make_branch(db_session, *, owner_id: str = "user-1") -> BranchOrm:
    """Create a Project + Branch so beats have a real FK target."""
    project = ProjectOrm(owner_id=owner_id, title="test project")
    db_session.add(project)
    await db_session.flush()
    branch = BranchOrm(project_id=project.id, name="main")
    db_session.add(branch)
    await db_session.flush()
    return branch


async def test_create_then_get_returns_it(db_session):
    branch = await _make_branch(db_session)
    repo = SqlBeatRepo(db_session)

    # Created is a beat object to be used
    created = await repo.create(
        branch_id=branch.id,
        sequence_index_in_branch=1,
        logline="Sarah finds a body at the pier",
        content={"scene": "pier", "mood": "tense"},
        valence=0.2,
        arousal=0.7,
    )

    assert created.logline == "Sarah finds a body at the pier"
    assert created.branch_id == branch.id
    assert created.status == "proposed"  # Default status is proposed if not declared
    # DB generates these two
    assert created.id is not None                  
    assert created.created_at is not None          

    # SELECT beat back and verify
    fetched = await repo.get(created.id, branch_id=branch.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.content == {"scene": "pier", "mood": "tense"}  

async def test_get_with_wrong_branch_returns_none(db_session):
    branch_a = await _make_branch(db_session)
    branch_b = await _make_branch(db_session)
    repo = SqlBeatRepo(db_session)

    created = await repo.create(
        branch_id=branch_a.id, sequence_index_in_branch=1, logline="...",
    )

    assert await repo.get(created.id, branch_id=branch_b.id) is None

async def test_get_with_wrong_branch_returns_none(db_session):
    # Build two branches
    branch_a = await _make_branch(db_session)
    branch_b = await _make_branch(db_session)
    # The repo, one instance
    repo = SqlBeatRepo(db_session)
    # Create a branch in beat A
    created = await repo.create(
        branch_id=branch_a.id, sequence_index_in_branch=1, logline="...",
    )
    # Basically give me beat x but scoped to branch B. Result should be none since we use wrong branch
    assert await repo.get(created.id, branch_id=branch_b.id) is None

# Fails safely
async def test_get_nonexistent_returns_none(db_session):
    branch = await _make_branch(db_session)
    repo = SqlBeatRepo(db_session)

    assert await repo.get(uuid.uuid4(), branch_id=branch.id) is None

# Test that list() properly sorts by sequence_index
async def test_list_orders_by_sequence_index(db_session):
    branch = await _make_branch(db_session)
    repo = SqlBeatRepo(db_session)

    # Insert out of order on purpose
    await repo.create(branch_id=branch.id, sequence_index_in_branch=3, logline="third")
    await repo.create(branch_id=branch.id, sequence_index_in_branch=1, logline="first")
    await repo.create(branch_id=branch.id, sequence_index_in_branch=2, logline="second")

    listed = await repo.list(branch_id=branch.id)
    assert [b.logline for b in listed] == ["first", "second", "third"]

async def test_list_scopes_to_branch(db_session):
    branch_a = await _make_branch(db_session)
    branch_b = await _make_branch(db_session)
    repo = SqlBeatRepo(db_session)

    await repo.create(branch_id=branch_a.id, sequence_index_in_branch=1, logline="A1")
    await repo.create(branch_id=branch_a.id, sequence_index_in_branch=2, logline="A2")
    await repo.create(branch_id=branch_b.id, sequence_index_in_branch=1, logline="B1")

    a_beats = await repo.list(branch_id=branch_a.id)
    assert {b.logline for b in a_beats} == {"A1", "A2"}


# set_status() can update status
async def test_set_status_commits_a_proposed_beat(db_session):
    branch = await _make_branch(db_session)
    repo = SqlBeatRepo(db_session)

    created = await repo.create(
        branch_id=branch.id, sequence_index_in_branch=1, logline="...",
    )
    assert created.status == "proposed"

    updated = await repo.set_status(created.id, "committed", branch_id=branch.id)
    assert updated.status == "committed"

# set_status fails loudly on missing rows when trying to update a beat that doesn't exist
async def test_set_status_on_missing_beat_raises(db_session):
    branch = await _make_branch(db_session)
    repo = SqlBeatRepo(db_session)

    with pytest.raises(ValueError):
        await repo.set_status(uuid.uuid4(), "committed", branch_id=branch.id)
