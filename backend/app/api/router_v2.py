"""router_v2: thin HTTP handlers for the v2 stack, one per endpoint.

A handler builds nothing and decides nothing; it injects the orchestrator and the
authenticated user, calls handle_turn, and maps a tenancy failure to a 403.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.clerk_gate import UserContext, get_current_user
from app.core.dependencies_v2 import get_orchestrator
from app.domain.models_v2 import TurnRequestV2, TurnResultV2
from app.services.orchestrator import ConversationOrchestrator, TurnAuthorizationError

router_v2 = APIRouter(tags=["v2"])


@router_v2.post("/conversation/turn", response_model=TurnResultV2)
async def post_turn(
    body: TurnRequestV2,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(get_current_user),
) -> TurnResultV2:
    try:
        return await orchestrator.handle_turn(body, owner_id=user.user_id)
    except TurnAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
