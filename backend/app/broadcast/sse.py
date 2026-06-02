"""
SSE endpoint — T-014.

The SSE route subscribes a client as an observer to EventBroadcaster.
It ONLY subscribes — it never calls broadcaster.publish().
Publishing happens exclusively inside ConversationOrchestrator (T-015).

Wire format: each event is `event: graph_delta\ndata: <json>\n\n`
Heartbeat comment every 15s keeps the connection alive through proxies.
"""
from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse  # type: ignore[import]

from app.auth.clerk_gate import UserContext, get_current_user
from app.broadcast.broadcaster import EventBroadcaster, get_broadcaster
from app.core.dependencies import get_story_repo
from app.repos.story_repo import StoryRepo

sse_router = APIRouter(tags=["sse"])

HEARTBEAT_INTERVAL = 15  # seconds


@sse_router.get(
    "/stories/{story_id}/events",
    summary="SSE stream of graph delta events for a story",
    response_class=EventSourceResponse,
)
async def story_events(
    story_id: UUID,
    broadcaster: EventBroadcaster = Depends(get_broadcaster),
    current_user: UserContext = Depends(get_current_user),
    story_repo: StoryRepo = Depends(get_story_repo),
) -> EventSourceResponse:
    """
    Subscribe to real-time GraphDeltaEvents for story_id.
    Only the story's owner may subscribe; anyone else gets a 404.
    Each event carries a monotonic sequence_number per (story, branch).
    """
    if await story_repo.get(story_id, owner_id=current_user.user_id) is None:
        # 404 not 403, so we do not leak which story ids exist
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="story not found")

    async def event_generator():
        subscription = await broadcaster.subscribe(story_id)
        try:
            async for event in subscription:
                yield {
                    "event": "graph_delta",
                    "data": event.model_dump_json(),
                }
        except asyncio.CancelledError:
            pass
        finally:
            await subscription.aclose()

    return EventSourceResponse(
        event_generator(),
        ping=HEARTBEAT_INTERVAL,
    )
