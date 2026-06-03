"""Integration tests for SqlCharacterRepo against a real Postgres (testcontainers)."""
import uuid

import pytest

from app.domain.orm_v2 import BeatCharacterOrm, BeatOrm, BranchOrm, ProjectOrm
from app.repos.character_repo import SqlCharacterRepo


async def _make_project(db_session, *, owner_id: str = "user-1") -> ProjectOrm:
    project = ProjectOrm(owner_id=owner_id, title="test project")
    db_session.add(project)
    await db_session.flush()
    return project


async def _make_branch(db_session, project_id) -> BranchOrm:
    branch = BranchOrm(project_id=project_id, name="main")
    db_session.add(branch)
    await db_session.flush()
    return branch


async def _make_beat(db_session, branch_id, sequence_index: int = 0) -> BeatOrm:
    beat = BeatOrm(branch_id=branch_id, sequence_index_in_branch=sequence_index, logline="test beat")
    db_session.add(beat)
    await db_session.flush()
    return beat


# tests for create / get / list
async def test_create_then_get_returns_it(db_session):
    project = await _make_project(db_session)
    repo = SqlCharacterRepo(db_session)

    created = await repo.create(
        project_id=project.id,
        name="Sarah",
        base_properties={"job": "detective", "age": 30},
    )

    assert created.name == "Sarah"
    assert created.project_id == project.id
    assert created.base_properties == {"job": "detective", "age": 30}
    assert created.status == "committed"   
    assert created.id is not None

    fetched = await repo.get(created.id, project_id=project.id)
    assert fetched is not None
    assert fetched.id == created.id


# Shouldn't be able to read across projects
async def test_get_with_wrong_project_returns_none(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project_a.id, name="Sarah")
    assert await repo.get(sarah.id, project_id=project_b.id) is None


# Missing id is None
async def test_get_nonexistent_returns_none(db_session):
    project = await _make_project(db_session)
    repo = SqlCharacterRepo(db_session)
    assert await repo.get(uuid.uuid4(), project_id=project.id) is None


# list() is properly scoped per project
async def test_list_scopes_to_project(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlCharacterRepo(db_session)

    await repo.create(project_id=project_a.id, name="Sarah")
    await repo.create(project_id=project_a.id, name="Tom")
    await repo.create(project_id=project_b.id, name="Other")

    a = await repo.list(project_id=project_a.id)
    assert {c.name for c in a} == {"Sarah", "Tom"}


# test set_base_properties 
# We can properly edit the past and update properly
async def test_set_base_properties_updates(db_session):
    project = await _make_project(db_session)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project.id, name="Sarah",
                              base_properties={"age": 30})

    updated = await repo.set_base_properties(
        sarah.id, {"age": 31, "job": "retired"}, project_id=project.id,
    )
    assert updated.base_properties == {"age": 31, "job": "retired"}


async def test_set_base_properties_on_missing_raises(db_session):
    project = await _make_project(db_session)
    repo = SqlCharacterRepo(db_session)

    with pytest.raises(ValueError):
        await repo.set_base_properties(uuid.uuid4(), {}, project_id=project.id)


# test upsert_overlay 
# We insert when no existing overlay is present, and can update that same overlay
async def test_upsert_overlay_inserts_then_updates(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project.id, name="Sarah",
                              base_properties={"age": 30})

    # Insert for the first time
    await repo.upsert_overlay(
        character_id=sarah.id, branch_id=branch.id, project_id=project.id,
        overlay_properties={"age": 45},
    )
    view1 = await repo.get_view(sarah.id, branch.id, project_id=project.id)
    assert view1.properties == {"age": 45}

    # Next insert is an update
    await repo.upsert_overlay(
        character_id=sarah.id, branch_id=branch.id, project_id=project.id,
        overlay_properties={"age": 50},
    )
    view2 = await repo.get_view(sarah.id, branch.id, project_id=project.id)
    assert view2.properties == {"age": 50}


# get_view (the merge)
# We just get our base traits back when no overlay is present
async def test_get_view_with_no_overlay_returns_base(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project.id, name="Sarah",
                              base_properties={"job": "detective", "age": 30})

    view = await repo.get_view(sarah.id, branch.id, project_id=project.id)
    assert view is not None
    assert view.properties == {"job": "detective", "age": 30}
    assert view.resolved_in_branch == branch.id

# Overlay overrides base on specific keys only
async def test_get_view_overlay_wins_on_key_conflict(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project.id, name="Sarah",
                              base_properties={"job": "detective", "age": 30})
    await repo.upsert_overlay(
        character_id=sarah.id, branch_id=branch.id, project_id=project.id,
        overlay_properties={"age": 45},
    )

    view = await repo.get_view(sarah.id, branch.id, project_id=project.id)
    assert view.properties == {"job": "detective", "age": 45}   


async def test_get_view_nonexistent_character_returns_none(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlCharacterRepo(db_session)

    assert await repo.get_view(uuid.uuid4(), branch.id, project_id=project.id) is None


# Cross-tenant attack, passing victim's character with attackers project_id returns None
async def test_get_view_with_wrong_project_returns_none(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    branch_a = await _make_branch(db_session, project_a.id)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project_a.id, name="Sarah",
                              base_properties={"job": "detective"})

    assert await repo.get_view(sarah.id, branch_a.id, project_id=project_b.id) is None


# Same attack on the write side, cross-tenant upsert should raise
async def test_upsert_overlay_with_wrong_project_raises(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    branch_a = await _make_branch(db_session, project_a.id)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project_a.id, name="Sarah")

    with pytest.raises(ValueError):
        await repo.upsert_overlay(
            character_id=sarah.id, branch_id=branch_a.id,
            project_id=project_b.id, overlay_properties={"age": 99},
        )


# list_for_beat returns only the characters linked to that beat
async def test_list_for_beat_returns_linked_characters(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    beat = await _make_beat(db_session, branch.id)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project.id, name="Sarah")
    await repo.create(project_id=project.id, name="Tom")
    db_session.add(BeatCharacterOrm(beat_id=beat.id, character_id=sarah.id))
    await db_session.flush()

    linked = await repo.list_for_beat(beat.id, project_id=project.id)
    assert {c.name for c in linked} == {"Sarah"}


# a link in project A never leaks when queried with project B's id
async def test_list_for_beat_scopes_to_project(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    branch_a = await _make_branch(db_session, project_a.id)
    beat_a = await _make_beat(db_session, branch_a.id)
    repo = SqlCharacterRepo(db_session)

    sarah = await repo.create(project_id=project_a.id, name="Sarah")
    db_session.add(BeatCharacterOrm(beat_id=beat_a.id, character_id=sarah.id))
    await db_session.flush()

    assert await repo.list_for_beat(beat_a.id, project_id=project_b.id) == []
