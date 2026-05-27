"""Integration tests for SqlThemeRepo against a real Postgres (testcontainers)."""
import uuid

import pytest

from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.theme_repo import SqlThemeRepo


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
    repo = SqlThemeRepo(db_session)

    created = await repo.create(
        project_id=project.id,
        name="Justice",
        base_properties={"weight": "heavy"},
    )

    assert created.name == "Justice"
    assert created.project_id == project.id
    assert created.base_properties == {"weight": "heavy"}
    assert created.status == "committed"
    assert created.id is not None

    fetched = await repo.get(created.id, project_id=project.id)
    assert fetched is not None
    assert fetched.id == created.id


# Shouldn't be able to read across projects
async def test_get_with_wrong_project_returns_none(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlThemeRepo(db_session)

    theme = await repo.create(project_id=project_a.id, name="Justice")
    assert await repo.get(theme.id, project_id=project_b.id) is None


# Missing id is None
async def test_get_nonexistent_returns_none(db_session):
    project = await _make_project(db_session)
    repo = SqlThemeRepo(db_session)
    assert await repo.get(uuid.uuid4(), project_id=project.id) is None


# list() is properly scoped per project
async def test_list_scopes_to_project(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    repo = SqlThemeRepo(db_session)

    await repo.create(project_id=project_a.id, name="Justice")
    await repo.create(project_id=project_a.id, name="Betrayal")
    await repo.create(project_id=project_b.id, name="Other")

    a = await repo.list(project_id=project_a.id)
    assert {t.name for t in a} == {"Justice", "Betrayal"}


# test set_base_properties 
# We can properly edit the past and update properly
async def test_set_base_properties_updates(db_session):
    project = await _make_project(db_session)
    repo = SqlThemeRepo(db_session)

    theme = await repo.create(project_id=project.id, name="Justice",
                              base_properties={"weight": "heavy"})

    updated = await repo.set_base_properties(
        theme.id, {"weight": "light", "tone": "ironic"}, project_id=project.id,
    )
    assert updated.base_properties == {"weight": "light", "tone": "ironic"}


async def test_set_base_properties_on_missing_raises(db_session):
    project = await _make_project(db_session)
    repo = SqlThemeRepo(db_session)

    with pytest.raises(ValueError):
        await repo.set_base_properties(uuid.uuid4(), {}, project_id=project.id)


# test upsert_overlay 
# We insert when no existing overlay is present, and can update that same overlay
async def test_upsert_overlay_inserts_then_updates(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlThemeRepo(db_session)

    theme = await repo.create(project_id=project.id, name="Justice",
                              base_properties={"weight": "heavy"})

    # Insert for the first time
    await repo.upsert_overlay(
        theme_id=theme.id, branch_id=branch.id, project_id=project.id,
        overlay_properties={"weight": "light"},
    )
    view1 = await repo.get_view(theme.id, branch.id, project_id=project.id)
    assert view1.properties == {"weight": "light"}

    # Next insert is an update
    await repo.upsert_overlay(
        theme_id=theme.id, branch_id=branch.id, project_id=project.id,
        overlay_properties={"weight": "absent"},
    )
    view2 = await repo.get_view(theme.id, branch.id, project_id=project.id)
    assert view2.properties == {"weight": "absent"}


# get_view (the merge)
# We just get our base traits back when no overlay is present
async def test_get_view_with_no_overlay_returns_base(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlThemeRepo(db_session)

    theme = await repo.create(project_id=project.id, name="Justice",
                              base_properties={"weight": "heavy", "tone": "grim"})

    view = await repo.get_view(theme.id, branch.id, project_id=project.id)
    assert view is not None
    assert view.properties == {"weight": "heavy", "tone": "grim"}
    assert view.resolved_in_branch == branch.id


# Overlay overrides base on specific keys only
async def test_get_view_overlay_wins_on_key_conflict(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlThemeRepo(db_session)

    theme = await repo.create(project_id=project.id, name="Justice",
                              base_properties={"weight": "heavy", "tone": "grim"})
    await repo.upsert_overlay(
        theme_id=theme.id, branch_id=branch.id, project_id=project.id,
        overlay_properties={"weight": "light"},
    )

    view = await repo.get_view(theme.id, branch.id, project_id=project.id)
    assert view.properties == {"weight": "light", "tone": "grim"}


async def test_get_view_nonexistent_theme_returns_none(db_session):
    project = await _make_project(db_session)
    branch = await _make_branch(db_session, project.id)
    repo = SqlThemeRepo(db_session)

    assert await repo.get_view(uuid.uuid4(), branch.id, project_id=project.id) is None


# Cross-tenant attack, passing victims theme with attackers project_id returns None
async def test_get_view_with_wrong_project_returns_none(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    branch_a = await _make_branch(db_session, project_a.id)
    repo = SqlThemeRepo(db_session)

    theme = await repo.create(project_id=project_a.id, name="Justice",
                              base_properties={"weight": "heavy"})

    assert await repo.get_view(theme.id, branch_a.id, project_id=project_b.id) is None


# Same attack on write side, cross-tenant upsert should raise
async def test_upsert_overlay_with_wrong_project_raises(db_session):
    project_a = await _make_project(db_session)
    project_b = await _make_project(db_session)
    branch_a = await _make_branch(db_session, project_a.id)
    repo = SqlThemeRepo(db_session)

    theme = await repo.create(project_id=project_a.id, name="Justice")

    with pytest.raises(ValueError):
        await repo.upsert_overlay(
            theme_id=theme.id, branch_id=branch_a.id,
            project_id=project_b.id, overlay_properties={"weight": "light"},
        )
