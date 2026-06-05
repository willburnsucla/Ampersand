"""No-database HTTP test for the v2 turn loop in mock mode.

Drives POST /api/v2/conversation/turn through the real app with NO get_v2_session
override, so under mock mode (conftest pins it) the orchestrator wires the
process-level InMemory repos and a turn round-trips with no Postgres. These tests
deliberately do not request the db_session fixture, so running this file alone
starts no testcontainer: that is the point, it proves make dev-mock can serve /api/v2.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.supabase_gate import UserContext, get_current_user
from app.core import dependencies_v2 as dv2
from app.main import app
from app.repos.beat_repo import InMemoryBeatRepo
from app.repos.branch_repo import InMemoryBranchRepo
from app.repos.character_repo import InMemoryCharacterRepo
from app.repos.conversation_repo import InMemoryConversationTurnRepo
from app.repos.issue_repo import InMemoryIssueRepo
from app.repos.project_repo import InMemoryProjectRepo
from app.repos.setting_repo import InMemorySettingRepo
from app.repos.theme_repo import InMemoryThemeRepo

OWNER = "mock-user"


@pytest.fixture(autouse=True)
def _fresh_singletons():
    # reset the process-level mock repos so each test starts empty and deterministic
    dv2._projects = InMemoryProjectRepo()
    dv2._branches = InMemoryBranchRepo()
    dv2._beats = InMemoryBeatRepo()
    dv2._characters = InMemoryCharacterRepo()
    dv2._themes = InMemoryThemeRepo()
    dv2._settings = InMemorySettingRepo()
    dv2._issues = InMemoryIssueRepo()
    dv2._conversations = InMemoryConversationTurnRepo()
    yield


def _client(*, owner: str = OWNER) -> AsyncClient:
    # override only the user; leave get_v2_session alone so mock mode yields no
    # session and the orchestrator routes to the InMemory repos (no Postgres)
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=owner)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_project_and_branch(*, owner: str = OWNER):
    project = await dv2._projects.create(title="mock story", owner_id=owner)
    branch = await dv2._branches.create(project_id=project.id, name="main")
    return project, branch


async def test_turn_writes_a_beat_with_no_database():
    project, branch = await _seed_project_and_branch()
    client = _client()
    try:
        resp = await client.post(
            "/api/v2/conversation/turn",
            json={
                "project_id": str(project.id),
                "branch_id": str(branch.id),
                "content": "the detective enters the forest",
            },
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"]
    assert body["beat"] is not None
    assert body["beat"]["status"] == "proposed"

    # the mock extractor links by keyword: detective -> Maya, forest -> The Dark Forest
    beat_id = uuid.UUID(body["beat"]["id"])
    chars = await dv2._characters.list_for_beat(beat_id, project_id=project.id)
    settings = await dv2._settings.list_for_beat(beat_id, project_id=project.id)
    assert {c.name for c in chars} == {"Maya"}
    assert {s.name for s in settings} == {"The Dark Forest"}


async def test_turn_short_message_asks_a_question_and_writes_no_beat():
    project, branch = await _seed_project_and_branch()
    client = _client()
    try:
        resp = await client.post(
            "/api/v2/conversation/turn",
            json={
                "project_id": str(project.id),
                "branch_id": str(branch.id),
                "content": "a fight",  # under the socratic word floor, so no beat
            },
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["beat"] is None
    assert body["reply"]


async def test_turn_rejects_wrong_owner():
    project, branch = await _seed_project_and_branch(owner="owner-a")
    client = _client(owner="intruder")
    try:
        resp = await client.post(
            "/api/v2/conversation/turn",
            json={
                "project_id": str(project.id),
                "branch_id": str(branch.id),
                "content": "the detective enters the forest",
            },
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert resp.status_code == 403


async def test_read_endpoints_run_in_mock_with_no_database():
    # lam's read surface goes through the same mock-aware providers, so it has to
    # round-trip with no database too, not just the conversation turn
    client = _client()
    try:
        created = await client.post(
            "/api/v2/projects",
            json={"title": "mock story"},
            headers={"Authorization": "Bearer mock"},
        )
        listed = await client.get(
            "/api/v2/projects",
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert created.status_code == 201
    project_id = created.json()["id"]
    assert listed.status_code == 200
    assert any(p["id"] == project_id for p in listed.json())


async def test_patch_beat_status_commits_a_proposed_beat():
    # a beat lands proposed; the PATCH is how the writer confirms it
    project, branch = await _seed_project_and_branch()
    beat = await dv2._beats.create(
        branch_id=branch.id, sequence_index_in_branch=0, logline="Maya enters"
    )
    assert beat.status == "proposed"
    client = _client()
    try:
        resp = await client.patch(
            f"/api/v2/projects/{project.id}/branches/{branch.id}/beats/{beat.id}",
            json={"status": "committed"},
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "committed"
    stored = await dv2._beats.get(beat.id, branch_id=branch.id)
    assert stored is not None and stored.status == "committed"


async def test_patch_beat_status_missing_beat_returns_404():
    project, branch = await _seed_project_and_branch()
    client = _client()
    try:
        resp = await client.patch(
            f"/api/v2/projects/{project.id}/branches/{branch.id}/beats/{uuid.uuid4()}",
            json={"status": "committed"},
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_delete_beat_endpoint_removes_it():
    # http-level cover for the delete fix: a deleted beat is gone from the list
    project, branch = await _seed_project_and_branch()
    beat = await dv2._beats.create(
        branch_id=branch.id, sequence_index_in_branch=0, logline="gone soon"
    )
    client = _client()
    try:
        resp = await client.delete(
            f"/api/v2/projects/{project.id}/branches/{branch.id}/beats/{beat.id}",
            headers={"Authorization": "Bearer mock"},
        )
        listed = await client.get(
            f"/api/v2/projects/{project.id}/branches/{branch.id}/beats",
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert resp.status_code == 204
    assert listed.status_code == 200
    assert listed.json() == []
