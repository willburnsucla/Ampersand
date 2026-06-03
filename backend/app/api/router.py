"""
FastAPI route handlers — T-016 (stubs) + T-004 inline dev orchestrator.

Each handler is ≤10 lines: dependency-inject, call service, serialize.
The conversation round-trip uses _DevOrchestrator in mock mode.
Once T-015 ships, swap in ConversationOrchestrator — no other changes needed.

Architectural invariants enforced:
  #3: Route handlers call orchestrator.handle_turn() — not Extractor/DeltaApplier/Broadcaster.
  #6: SSE push happens only inside the orchestrator (via broadcaster.publish()).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.supabase_gate import UserContext, get_current_user
from app.broadcast.broadcaster import EventBroadcaster, get_broadcaster
from app.security import PromptSecurityManager, SecurityException
from app.core.dependencies import (
    get_branch_repo,
    get_conversation_repo,
    get_extractor,
    get_graph_repo,
    get_prompt_security_manager,
    get_provenance_index,
    get_story_repo,
)
from app.domain.models import (
    Branch,
    BranchTransitionInput,
    ConversationTurn,
    CreateBranchInput,
    CreateStoryInput,
    GraphDeltaEvent,
    GraphSnapshot,
    Story,
    TurnRequest,
    TurnResult,
)
from app.domain.branch_state_machine import BranchEvent, InvalidTransitionError
from app.repos.branch_repo import BranchRepo
from app.repos.conversation_repo import ConversationRepo
from app.repos.graph_repo import GraphRepo
from app.repos.provenance_index import ProvenanceIndex
from app.repos.story_repo import StoryRepo
from app.services.extractor import Extractor, LlmContext

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {"status": "ok"}


# ── Stories ───────────────────────────────────────────────────────────────────

@router.post("/stories", response_model=Story, status_code=status.HTTP_201_CREATED, tags=["stories"])
async def create_story(
    body: CreateStoryInput,
    story_repo: StoryRepo = Depends(get_story_repo),
    current_user: UserContext = Depends(get_current_user),
) -> Story:
    return await story_repo.create(body, owner_id=current_user.user_id)


@router.get("/stories", response_model=list[Story], tags=["stories"])
async def list_stories(
    story_repo: StoryRepo = Depends(get_story_repo),
    current_user: UserContext = Depends(get_current_user),
) -> list[Story]:
    return await story_repo.list(owner_id=current_user.user_id)


# ── Graph snapshot ────────────────────────────────────────────────────────────

@router.get("/stories/{story_id}/graph", response_model=GraphSnapshot, tags=["graph"])
async def get_graph(
    story_id: UUID,
    branch_id: UUID,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    broadcaster: EventBroadcaster = Depends(get_broadcaster),
    current_user: UserContext = Depends(get_current_user),
) -> GraphSnapshot:
    # Read sequence BEFORE snapshot so client never overshoots
    last_seq = broadcaster.get_latest_sequence(story_id, branch_id)
    scoped = await graph_repo.for_branch(branch_id)
    nodes = await scoped.list_nodes()
    edges = await scoped.list_edges()
    return GraphSnapshot(
        story_id=story_id,
        branch_id=branch_id,
        nodes=nodes,
        edges=edges,
        last_applied_sequence=last_seq,
        generated_at=datetime.utcnow(),
    )


# ── Branches ──────────────────────────────────────────────────────────────────

@router.post("/branches", response_model=Branch, status_code=status.HTTP_201_CREATED, tags=["branches"])
async def create_branch(
    body: CreateBranchInput,
    branch_repo: BranchRepo = Depends(get_branch_repo),
    current_user: UserContext = Depends(get_current_user),
) -> Branch:
    return await branch_repo.create(body)


@router.get("/stories/{story_id}/branches", response_model=list[Branch], tags=["branches"])
async def list_branches(
    story_id: UUID,
    branch_repo: BranchRepo = Depends(get_branch_repo),
    current_user: UserContext = Depends(get_current_user),
) -> list[Branch]:
    return await branch_repo.list(story_id=story_id)


@router.post("/branches/{branch_id}/transition", response_model=Branch, tags=["branches"])
async def transition_branch(
    branch_id: UUID,
    body: BranchTransitionInput,
    branch_repo: BranchRepo = Depends(get_branch_repo),
    current_user: UserContext = Depends(get_current_user),
) -> Branch:
    try:
        event = BranchEvent(body.event)
        return await branch_repo.transition(branch_id, event)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")


# ── Conversation (T-004 inline dev orchestrator) ──────────────────────────────

@router.post("/conversation/turn", response_model=TurnResult, tags=["conversation"])
async def post_turn(
    body: TurnRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    story_repo: StoryRepo = Depends(get_story_repo),
    branch_repo: BranchRepo = Depends(get_branch_repo),
    conv_repo: ConversationRepo = Depends(get_conversation_repo),
    prov_index: ProvenanceIndex = Depends(get_provenance_index),
    extractor: Extractor = Depends(get_extractor),
    broadcaster: EventBroadcaster = Depends(get_broadcaster),
    security_manager: PromptSecurityManager = Depends(get_prompt_security_manager),
    current_user: UserContext = Depends(get_current_user),
) -> TurnResult:
    """
    Inline dev orchestrator (T-004).
    Mirrors the ConversationOrchestrator (T-015) step sequence exactly.
    Swap for real orchestrator once T-015 ships.
    """
    # 1. Persist writer turn
    turn_id = uuid.uuid4()
    writer_turn = ConversationTurn(
        id=turn_id,
        story_id=body.story_id,
        branch_id=body.branch_id,
        role="writer",
        content=body.content,
        created_at=datetime.utcnow(),
    )
    await conv_repo.append_turn(writer_turn)

    # 2. Build minimal LlmContext (full ContextBuilder T-007 not yet wired)
    ctx = LlmContext(
        user_message=body.content,
        branch_summary="",
        recent_turns=[],
        relevant_nodes=[],
    )

    # 2.5. Sanitize and validate context (Prompt Security Manager)
    try:
        ctx = await security_manager.process_context(ctx, body.story_id, body.branch_id)
    except SecurityException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.sanitized_message,
        ) from exc

    # 3. Extract (MockExtractor or ClaudeExtractor depending on mode)
    result = await extractor.extract(ctx, turn_id=turn_id)

    # 4. Patch story_id + branch_tags on all nodes in the delta
    for op in result.delta.ops:
        if hasattr(op, "node"):
            op.node.story_id = body.story_id
            if body.branch_id not in op.node.branch_tags:
                op.node.branch_tags.append(body.branch_id)
        if hasattr(op, "edge"):
            if body.branch_id not in op.edge.branch_tags:
                op.edge.branch_tags.append(body.branch_id)

    # 5. Apply delta
    scoped = await graph_repo.for_branch(body.branch_id)
    applied = await scoped.apply_delta(result.delta)

    # 6. Persist assistant reply
    assistant_turn = ConversationTurn(
        id=uuid.uuid4(),
        story_id=body.story_id,
        branch_id=body.branch_id,
        role="assistant",
        content=result.reply,
        created_at=datetime.utcnow(),
    )
    await conv_repo.append_turn(assistant_turn)

    # 7. Record provenance
    await prov_index.record(turn_id, applied.affected_node_ids, applied.affected_edge_ids)

    # 8. Publish SSE event (invariant #6: only here, not in broadcaster.subscribe)
    event = GraphDeltaEvent(
        schema_version=1,
        story_id=body.story_id,
        branch_id=body.branch_id,
        turn_id=turn_id,
        sequence_number=1,  # broadcaster overwrites
        applied_ops=result.delta.ops,
        timestamp=datetime.utcnow(),
    )
    await broadcaster.publish(event)

    return TurnResult(
        turn_id=turn_id,
        reply=result.reply,
        applied_delta=applied,
    )
