"""Integration tests for SqlBranchRepo against a real Postgres (testcontainers)."""
import uuid

import pytest

from app.domain.branch_state_machine import BranchEvent, InvalidTransitionError
from app.domain.orm_v2 import BeatOrm, ProjectOrm
from app.repos.branch_repo import SqlBranchRepo


async def _make_project(db_session, *, owner_id: str = "user-1") -> ProjectOrm:
    project = ProjectOrm(owner_id=owner_id, title="test project")
    db_session.add(project)
    await db_session.flush()
    return project


async def _make_beat(db_session, branch_id, sequence_index: int = 0) -> BeatOrm:
    beat = BeatOrm(
        branch_id=branch_id,
        sequence_index_in_branch=sequence_index,
        logline="test beat",
    )
    db_session.add(beat)
    await db_session.flush()
    return beat


async def test_create_then_get_returns_it(db_session):
    project = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    created = await repo.create(project_id=project.id, name="main")

    assert created.name == "main"
    assert created.project_id == project.id
    assert created.state == "active"        
    assert created.id is not None
    assert created.created_at is not None

    fetched = await repo.get(created.id, project_id=project.id)
    assert fetched is not None
    assert fetched.id == created.id


async def test_get_with_wrong_project_returns_none(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    created = await repo.create(project_id=project_a.id, name="main")

    assert await repo.get(created.id, project_id=project_b.id) is None


async def test_list_scopes_to_project(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    await repo.create(project_id=project_a.id, name="A1")
    await repo.create(project_id=project_a.id, name="A2")
    await repo.create(project_id=project_b.id, name="B1")

    a_branches = await repo.list(project_id=project_a.id)
    assert {b.name for b in a_branches} == {"A1", "A2"}


async def test_transition_active_to_dormant(db_session):
    project = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    branch = await repo.create(project_id=project.id, name="main")
    assert branch.state == "active"

    updated = await repo.transition(branch.id, BranchEvent.SWITCH_TO_DORMANT, project_id=project.id)
    assert updated.state == "dormant"
  
async def test_transition_graveyard_to_active_by_revive(db_session):
    project = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)
    
    branch = await repo.create(project_id=project.id, name="main")
    # active to graveyard
    await repo.transition(branch.id, BranchEvent.ABANDON, project_id=project.id)
    # graveyard to active
    updated = await repo.transition(branch.id, BranchEvent.REVIVE, project_id=project.id)
    assert updated.state == "active"


async def test_transition_illegal_raises(db_session):
    project = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    branch = await repo.create(project_id=project.id, name="main")

    # we can't revive an active branch, only one in graveyard
    with pytest.raises(InvalidTransitionError):
        await repo.transition(branch.id, BranchEvent.REVIVE, project_id=project.id)


async def test_transition_on_missing_branch_raises(db_session):
    project = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    with pytest.raises(ValueError):
        await repo.transition(uuid.uuid4(), BranchEvent.COMMIT, project_id=project.id)


# fork cap, 3 alternates from same beat succeed, 4th raises
async def test_create_fork_caps_at_three_per_beat(db_session):
    project = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    parent = await repo.create(project_id=project.id, name="main")
    fork_beat = await _make_beat(db_session, parent.id)

    for i in range(3):
        await repo.create_fork(
            project_id=project.id,
            parent_branch_id=parent.id,
            created_from_beat_id=fork_beat.id,
            name=f"alt-{i}",
        )

    with pytest.raises(ValueError, match="cap is 3"):
        await repo.create_fork(
            project_id=project.id,
            parent_branch_id=parent.id,
            created_from_beat_id=fork_beat.id,
            name="alt-4",
        )


# the cap is per fork beat, so different beats each get their own quota
async def test_create_fork_cap_is_per_beat(db_session):
    project = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    parent = await repo.create(project_id=project.id, name="main")
    beat_a = await _make_beat(db_session, parent.id, sequence_index=0)
    beat_b = await _make_beat(db_session, parent.id, sequence_index=1)

    for i in range(3):
        await repo.create_fork(
            project_id=project.id,
            parent_branch_id=parent.id,
            created_from_beat_id=beat_a.id,
            name=f"a-{i}",
        )

    fork_b = await repo.create_fork(
        project_id=project.id,
        parent_branch_id=parent.id,
        created_from_beat_id=beat_b.id,
        name="b-0",
    )
    assert fork_b.created_from_beat_id == beat_b.id


# cross tenant attack, parent from project A but caller passes project_id B
async def test_create_fork_cross_tenant_raises(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlBranchRepo(db_session)

    parent = await repo.create(project_id=project_a.id, name="main")
    fork_beat = await _make_beat(db_session, parent.id)

    with pytest.raises(ValueError):
        await repo.create_fork(
            project_id=project_b.id,
            parent_branch_id=parent.id,
            created_from_beat_id=fork_beat.id,
            name="sneaky",
        )
