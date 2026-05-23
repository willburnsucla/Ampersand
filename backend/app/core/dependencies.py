"""
Dependency injection wiring.

Reads AMPERSAND_BACKEND_MODE to select InMemory vs Postgres implementations.
All module-level singletons are instantiated once at import time.
Route handlers NEVER import repos directly — they use these dependency functions.
"""
from app.core.config import settings
from app.repos.graph_repo import GraphRepo, InMemoryGraphRepo, PostgresGraphRepo
from app.repos.story_repo import InMemoryStoryRepo, PostgresStoryRepo, StoryRepo
from app.repos.branch_repo import BranchRepo, InMemoryBranchRepo, PostgresBranchRepo

from app.repos.provenance_index import (
    InMemoryProvenanceIndex,
    PostgresProvenanceIndex,
    ProvenanceIndex,
)
from app.services.extractor import ClaudeExtractor, Extractor, MockExtractor

from app.repos.conversation_repo import ConversationTurnRepo, SqlConversationTurnRepo

from app.repos.project_repo import ProjectRepo, SqlProjectRepo

# ── InMemory singletons (shared state for the lifetime of the process) ────────
_graph_repo = InMemoryGraphRepo()
_story_repo = InMemoryStoryRepo()
_branch_repo = InMemoryBranchRepo()
_prov_index = InMemoryProvenanceIndex()
_mock_extractor = MockExtractor()

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db


# ── Dependency provider functions (used with FastAPI Depends()) ───────────────

def get_graph_repo() -> GraphRepo:
    if settings.is_mock:
        return _graph_repo
    # PostgresGraphRepo needs a DB session; injected differently in real mode
    raise NotImplementedError("Real mode not yet wired — use AMPERSAND_BACKEND_MODE=mock")


def get_story_repo() -> StoryRepo:
    if settings.is_mock:
        return _story_repo
    raise NotImplementedError("Real mode not yet wired")


def get_branch_repo() -> BranchRepo:
    if settings.is_mock:
        return _branch_repo
    raise NotImplementedError("Real mode not yet wired")

def get_provenance_index() -> ProvenanceIndex:
    if settings.is_mock:
        return _prov_index
    raise NotImplementedError("Real mode not yet wired")


def get_extractor() -> Extractor:
    if settings.is_mock:
        return _mock_extractor
    return ClaudeExtractor()

def get_conversation_repo(session: AsyncSession = Depends(get_db)) -> ConversationTurnRepo:
    if settings.is_mock:
        raise NotImplementedError("ConversationTurnRepo has no mock implementation; use real mode")
    return SqlConversationTurnRepo(session)

def get_project_repo(session: AsyncSession = Depends(get_db)) -> ProjectRepo:
    if settings.is_mock:
        raise NotImplementedError("ProjectRepo has no mock implementation; use real mode")
    return SqlProjectRepo(session)
