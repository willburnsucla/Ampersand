"""router_v2: thin HTTP handlers for the v2 stack, one per endpoint.

A handler builds nothing and decides nothing; it injects the repo/orchestrator
and the authenticated user, calls the method, and maps auth/tenancy failures to
HTTP status codes.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.supabase_gate import UserContext, get_current_user
from app.core.dependencies import get_prompt_security_manager
from app.security import PromptSecurityManager, SecurityException
from app.services.extractor import LlmContext
from app.core.dependencies_v2 import (
    get_beat_repo,
    get_branch_repo_v2,
    get_character_repo,
    get_conversation_repo,
    get_issue_repo,
    get_orchestrator,
    get_project_repo,
    get_setting_repo,
    get_theme_repo,
)
from app.domain.models_v2 import (
    Beat,
    Branch,
    Character,
    ConversationTurn,
    Issue,
    Project,
    Setting,
    Theme,
    TurnRequestV2,
    TurnResultV2,
)
from app.repos.beat_repo import SqlBeatRepo
from app.repos.branch_repo import SqlBranchRepo
from app.repos.character_repo import SqlCharacterRepo
from app.repos.conversation_repo import SqlConversationTurnRepo
from app.repos.issue_repo import SqlIssueRepo
from app.repos.project_repo import SqlProjectRepo
from app.repos.setting_repo import SqlSettingRepo
from app.repos.theme_repo import SqlThemeRepo
from app.services.orchestrator import ConversationOrchestrator, TurnAuthorizationError
from pydantic import BaseModel

router_v2 = APIRouter(tags=["v2"])


# Projects

class CreateProjectBody(BaseModel):
    title: str


@router_v2.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectBody,
    repo: SqlProjectRepo = Depends(get_project_repo),
    user: UserContext = Depends(get_current_user),
) -> Project:
    return await repo.create(title=body.title, owner_id=user.user_id)


@router_v2.get("/projects", response_model=list[Project])
async def list_projects(
    repo: SqlProjectRepo = Depends(get_project_repo),
    user: UserContext = Depends(get_current_user),
) -> list[Project]:
    return await repo.list(owner_id=user.user_id)


# Branches

class CreateBranchBody(BaseModel):
    project_id: UUID
    name: str | None = None
    parent_branch_id: UUID | None = None
    created_from_beat_id: UUID | None = None


@router_v2.post("/branches", response_model=Branch, status_code=status.HTTP_201_CREATED)
async def create_branch(
    body: CreateBranchBody,
    projects: SqlProjectRepo = Depends(get_project_repo),
    branches: SqlBranchRepo = Depends(get_branch_repo_v2),
    user: UserContext = Depends(get_current_user),
) -> Branch:
    project = await projects.get(body.project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await branches.create(
        project_id=body.project_id,
        name=body.name,
        parent_branch_id=body.parent_branch_id,
        created_from_beat_id=body.created_from_beat_id,
    )


@router_v2.get("/projects/{project_id}/branches", response_model=list[Branch])
async def list_branches(
    project_id: UUID,
    projects: SqlProjectRepo = Depends(get_project_repo),
    branches: SqlBranchRepo = Depends(get_branch_repo_v2),
    user: UserContext = Depends(get_current_user),
) -> list[Branch]:
    project = await projects.get(project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await branches.list(project_id=project_id)


# Beats 

@router_v2.get("/projects/{project_id}/branches/{branch_id}/beats", response_model=list[Beat])
async def list_beats(
    project_id: UUID,
    branch_id: UUID,
    projects: SqlProjectRepo = Depends(get_project_repo),
    branches: SqlBranchRepo = Depends(get_branch_repo_v2),
    beats: SqlBeatRepo = Depends(get_beat_repo),
    user: UserContext = Depends(get_current_user),
) -> list[Beat]:
    project = await projects.get(project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    branch = await branches.get(branch_id, project_id=project_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return await beats.list(branch_id=branch_id)


# Characters

@router_v2.get("/projects/{project_id}/characters", response_model=list[Character])
async def list_characters(
    project_id: UUID,
    projects: SqlProjectRepo = Depends(get_project_repo),
    characters: SqlCharacterRepo = Depends(get_character_repo),
    user: UserContext = Depends(get_current_user),
) -> list[Character]:
    project = await projects.get(project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await characters.list(project_id=project_id)


# Themes

@router_v2.get("/projects/{project_id}/themes", response_model=list[Theme])
async def list_themes(
    project_id: UUID,
    projects: SqlProjectRepo = Depends(get_project_repo),
    themes: SqlThemeRepo = Depends(get_theme_repo),
    user: UserContext = Depends(get_current_user),
) -> list[Theme]:
    project = await projects.get(project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await themes.list(project_id=project_id)


# Settings

@router_v2.get("/projects/{project_id}/settings", response_model=list[Setting])
async def list_settings(
    project_id: UUID,
    projects: SqlProjectRepo = Depends(get_project_repo),
    settings: SqlSettingRepo = Depends(get_setting_repo),
    user: UserContext = Depends(get_current_user),
) -> list[Setting]:
    project = await projects.get(project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await settings.list(project_id=project_id)


# Issues

@router_v2.get("/projects/{project_id}/branches/{branch_id}/issues", response_model=list[Issue])
async def list_issues(
    project_id: UUID,
    branch_id: UUID,
    projects: SqlProjectRepo = Depends(get_project_repo),
    branches: SqlBranchRepo = Depends(get_branch_repo_v2),
    issues: SqlIssueRepo = Depends(get_issue_repo),
    user: UserContext = Depends(get_current_user),
) -> list[Issue]:
    project = await projects.get(project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    branch = await branches.get(branch_id, project_id=project_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return await issues.list(branch_id=branch_id)


# Conversation turns

@router_v2.get("/projects/{project_id}/branches/{branch_id}/turns", response_model=list[ConversationTurn])
async def list_turns(
    project_id: UUID,
    branch_id: UUID,
    projects: SqlProjectRepo = Depends(get_project_repo),
    branches: SqlBranchRepo = Depends(get_branch_repo_v2),
    conversations: SqlConversationTurnRepo = Depends(get_conversation_repo),
    user: UserContext = Depends(get_current_user),
) -> list[ConversationTurn]:
    project = await projects.get(project_id, owner_id=user.user_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    branch = await branches.get(branch_id, project_id=project_id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    turns = await conversations.list_turns(branch_id, limit=50)
    return list(reversed(turns))  # list_turns returns newest-first; return chronological


# Conversation turn (main orchestrator entry)

@router_v2.post("/conversation/turn", response_model=TurnResultV2)
async def post_turn(
    body: TurnRequestV2,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
    user: UserContext = Depends(get_current_user),
    security_manager: PromptSecurityManager = Depends(get_prompt_security_manager),
) -> TurnResultV2:
    ctx = LlmContext(user_message=body.content, branch_summary="", recent_turns=[], relevant_nodes=[])
    try:
        await security_manager.process_context(ctx, body.project_id, body.branch_id)
    except SecurityException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.sanitized_message) from exc

    try:
        return await orchestrator.handle_turn(body, owner_id=user.user_id)
    except TurnAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
