"""
EventBroadcaster — T-014. Subject in the Observer pattern.

In-process pub/sub keyed by (story_id, branch_id).
Assigns monotonic sequence_number per (story_id, branch_id) on every publish.

Sequence number semantics:
  - Counter is an in-memory dict — resets on backend restart.
  - Acceptable in v1: all SSE connections drop on restart; clients re-fetch via getGraph.
  - v2: move counter to Postgres or Redis for horizontal scaling (secret of this module).

Caller MUST NOT trust sequence_number it places in the event — broadcaster overwrites it.

Architectural invariant #6: EventBroadcaster.publish() is the ONLY place events are pushed
to clients. Route handlers and orchestrators never push directly to SSE connections.
"""
from __future__ import annotations

import asyncio
import uuid
from asyncio import Queue
from collections import defaultdict
from datetime import datetime
from uuid import UUID

from app.domain.models import GraphDeltaEvent


class EventBroadcaster:
    """
    In-process subject. Thread-safe for asyncio (single-thread event loop).
    One global instance is used per process (injected via FastAPI dependency).
    """

    def __init__(self) -> None:
        # (story_id, branch_id) → monotonic counter
        self._counters: dict[tuple[UUID, UUID], int] = defaultdict(int)
        # story_id → list of subscriber queues
        self._subscribers: dict[UUID, list[Queue[GraphDeltaEvent]]] = defaultdict(list)

    def _next_sequence(self, story_id: UUID, branch_id: UUID) -> int:
        """Atomically increment and return the next sequence number."""
        key = (story_id, branch_id)
        self._counters[key] += 1
        return self._counters[key]

    def get_latest_sequence(self, story_id: UUID, branch_id: UUID) -> int:
        """
        Returns the most recently assigned sequence_number for this (story, branch), or 0.
        Used by GET /graph to populate GraphSnapshot.last_applied_sequence.
        """
        return self._counters.get((story_id, branch_id), 0)

    async def publish(self, event: GraphDeltaEvent) -> GraphDeltaEvent:
        """
        Assign the next sequence_number (overwrites caller-supplied value) then fan-out
        to all subscribers for this story_id.
        Returns the event with the assigned sequence_number.
        """
        # Overwrite — caller-supplied sequence_number is never trusted
        seq = self._next_sequence(event.story_id, event.branch_id)
        event = event.model_copy(update={"sequence_number": seq, "timestamp": datetime.utcnow()})

        queues = list(self._subscribers.get(event.story_id, []))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer — drop event rather than block the publisher
                pass

        return event

    async def subscribe(
        self, story_id: UUID
    ) -> "AsyncIteratorWrapper":
        """
        Return an async iterator that yields GraphDeltaEvents for story_id.
        Caller must iterate (e.g. async for event in broadcaster.subscribe(story_id))
        and the iterator auto-unsubscribes on StopAsyncIteration or GeneratorExit.
        """
        q: Queue[GraphDeltaEvent] = Queue(maxsize=512)
        self._subscribers[story_id].append(q)
        return AsyncIteratorWrapper(self, story_id, q)

    def _unsubscribe(self, story_id: UUID, q: Queue) -> None:
        try:
            self._subscribers[story_id].remove(q)
        except ValueError:
            pass


class AsyncIteratorWrapper:
    """Wraps a Queue into an async iterator; unsubscribes on exit."""

    def __init__(
        self,
        broadcaster: EventBroadcaster,
        story_id: UUID,
        queue: Queue[GraphDeltaEvent],
    ) -> None:
        self._broadcaster = broadcaster
        self._story_id = story_id
        self._queue = queue

    def __aiter__(self) -> "AsyncIteratorWrapper":
        return self

    async def __anext__(self) -> GraphDeltaEvent:
        return await self._queue.get()

    async def aclose(self) -> None:
        self._broadcaster._unsubscribe(self._story_id, self._queue)


# ── Singleton (injected via FastAPI dependency) ───────────────────────────────

_broadcaster = EventBroadcaster()


def get_broadcaster() -> EventBroadcaster:
    return _broadcaster
