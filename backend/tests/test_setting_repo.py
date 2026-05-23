"""Integration tests for SqlSettingRepo against a real Postgres (testcontainers)."""
import uuid

import pytest

from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.setting_repo import SqlSettingRepo

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

# tests for create / get / list

async def test_create_then_get_returns_it(db_session):
    project = await _make_project(db_session)
    repo = SqlSettingRepo(db_session)

    created = await repo.create(
        project_id=project.id,
        name="the pier",
        base_properties={"time": "night", "weather": "fog"},
    )

    assert created.name == "the pier"
    assert created.base_properties == {"time": "night", "weather": "fog"}
    assert created.status == "committed"
    assert created.id is not None

    fetched = await repo.get(created.id, project_id=project.id)
    assert fetched is not None
    assert fetched.id == created.id

# Shouldn't be able to read across projects
async def test_get_with_wrong_project_returns_none(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlSettingRepo(db_session)

    s = await repo.create(project_id=project_a.id, name="the pier")
    assert await repo.get(s.id, project_id=project_b.id) is None

# Missing id is None
async def test_get_nonexistent_returns_none(db_session):
    project = await _make_project(db_session)
    repo = SqlSettingRepo(db_session)
    assert await repo.get(uuid.uuid4(), project_id=project.id) is None

# list() is properly scoped per project
async def test_list_scopes_to_project(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlSettingRepo(db_session)

    await repo.create(project_id=project_a.id, name="the pier")
    await repo.create(project_id=project_a.id, name="the manor")
    await repo.create(project_id=project_b.id, name="other")

    a = await repo.list(project_id=project_a.id)
    assert {s.name for s in a} == {"the pier", "the manor"}

# test set_base_properties
# We can properly edit canon and update properly
async def test_set_base_properties_updates(db_session):
    project = await _make_project(db_session)
    repo = SqlSettingRepo(db_session)

    s = await repo.create(project_id=project.id, name="the pier",
                          base_properties={"time": "night"})

    updated = await repo.set_base_properties(
        s.id, {"time": "dawn", "weather": "clear"}, project_id=project.id,
    )
    assert updated.base_properties == {"time": "dawn", "weather": "clear"}

async def test_set_base_properties_on_missing_raises(db_session):
    project = await _make_project(db_session)
    repo = SqlSettingRepo(db_session)

    with pytest.raises(ValueError):
        await repo.set_base_properties(uuid.uuid4(), {}, project_id=project.id)

# test upsert_overlay
# We insert when no existing overlay is present, and can update that same overlay
async def test_upsert_overlay_inserts_then_updates(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlSettingRepo(db_session)

    s = await repo.create(project_id=project.id, name="the pier",
                          base_properties={"time": "night"})

    # Insert for the first time
    await repo.upsert_overlay(
        setting_id=s.id, branch_id=branch.id, overlay_properties={"time": "dawn"},
    )
    view1 = await repo.get_view(s.id, branch.id)
    assert view1.properties == {"time": "dawn"}

    # Next insert is an update
    await repo.upsert_overlay(
        setting_id=s.id, branch_id=branch.id, overlay_properties={"time": "noon"},
    )
    view2 = await repo.get_view(s.id, branch.id)
    assert view2.properties == {"time": "noon"}

# get_view (the merge)
# We just get our base traits back when no overlay is present
async def test_get_view_with_no_overlay_returns_base(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlSettingRepo(db_session)

    s = await repo.create(project_id=project.id, name="the pier",
                          base_properties={"time": "night", "weather": "fog"})

    view = await repo.get_view(s.id, branch.id)
    assert view is not None
    assert view.properties == {"time": "night", "weather": "fog"}
    assert view.resolved_in_branch == branch.id

# Overlay overrides base on specific keys only
async def test_get_view_overlay_wins_on_key_conflict(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlSettingRepo(db_session)

    s = await repo.create(project_id=project.id, name="the pier",
                          base_properties={"time": "night", "weather": "fog"})
    await repo.upsert_overlay(
        setting_id=s.id, branch_id=branch.id, overlay_properties={"time": "dawn"},
    )

    view = await repo.get_view(s.id, branch.id)
    assert view.properties == {"time": "dawn", "weather": "fog"}

async def test_get_view_nonexistent_setting_returns_none(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlSettingRepo(db_session)

    assert await repo.get_view(uuid.uuid4(), branch.id) is None
