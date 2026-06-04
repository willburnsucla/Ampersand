"""End-to-end HTTP tests for router_v2.

Drives POST /api/v2/conversation/turn through the real app, with get_db overridden
to the test session and a stubbed authenticated user, so the route runs the whole
turn loop against Postgres.
"""
import uuid

from httpx import ASGITransport, AsyncClient

from app.auth.supabase_gate import UserContext, get_current_user
from app.core.dependencies_v2 import get_v2_session
from app.main import app
from app.repos.branch_repo import SqlBranchRepo
from app.repos.character_repo import SqlCharacterRepo
from app.repos.project_repo import SqlProjectRepo


def _wire_app(db_session, *, owner: str) -> AsyncClient:
    # override the v2 session seam so the orchestrator wires sql repos on the test
    # session (mock mode would otherwise route to the process-level InMemory repos)
    app.dependency_overrides[get_v2_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id=owner)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _project_and_branch(db_session, *, owner: str = "user-1"):
    project = await SqlProjectRepo(db_session).create(title="proj", owner_id=owner)
    branch = await SqlBranchRepo(db_session).create(project_id=project.id, name="main")
    return project, branch


async def test_turn_endpoint_writes_a_beat(db_session):
    project, branch = await _project_and_branch(db_session)
    client = _wire_app(db_session, owner="user-1")
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
    assert body["beat"]["status"] == "proposed"
    assert body["reply"]

    chars = await SqlCharacterRepo(db_session).list_for_beat(
        uuid.UUID(body["beat"]["id"]), project_id=project.id
    )
    assert {c.name for c in chars} == {"Maya"}


async def test_turn_endpoint_rejects_wrong_owner(db_session):
    project, branch = await _project_and_branch(db_session, owner="user-1")
    client = _wire_app(db_session, owner="intruder")
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


async def test_turn_endpoint_validates_body(db_session):
    client = _wire_app(db_session, owner="user-1")
    try:
        resp = await client.post(
            "/api/v2/conversation/turn",
            json={"project_id": str(uuid.uuid4()), "branch_id": str(uuid.uuid4())},
            headers={"Authorization": "Bearer mock"},
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()

    assert resp.status_code == 422
