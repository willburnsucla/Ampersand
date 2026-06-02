"""HTTP test for the SSE ownership guard on GET /api/v1/stories/{id}/events."""
from httpx import ASGITransport, AsyncClient

from app.auth.clerk_gate import UserContext, get_current_user
from app.core.dependencies import get_story_repo
from app.domain.models import CreateStoryInput
from app.main import app
from app.repos.story_repo import InMemoryStoryRepo


# a writer who does not own the story cannot subscribe to its event stream
async def test_sse_rejects_non_owner():
    repo = InMemoryStoryRepo()
    story = await repo.create(CreateStoryInput(title="proj"), owner_id="owner-1")

    app.dependency_overrides[get_story_repo] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: UserContext(user_id="intruder")
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/api/v1/stories/{story.id}/events",
                headers={"Authorization": "Bearer mock"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
