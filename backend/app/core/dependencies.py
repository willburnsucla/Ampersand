"""
Dependency injection wiring.

Reads AMPERSAND_BACKEND_MODE to select InMemory vs Postgres implementations.
All module-level singletons are instantiated once at import time.
Route handlers NEVER import repos directly, they use these dependency functions.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.repos.beat_repo import BeatRepo, SqlBeatRepo
from app.repos.branch_repo import BranchRepo, InMemoryBranchRepo, PostgresBranchRepo
from app.repos.character_repo import CharacterRepo, SqlCharacterRepo
from app.repos.conversation_repo import ConversationTurnRepo, SqlConversationTurnRepo
from app.repos.graph_repo import GraphRepo, InMemoryGraphRepo, PostgresGraphRepo
from app.repos.issue_repo import IssueRepo, SqlIssueRepo
from app.repos.project_repo import ProjectRepo, SqlProjectRepo
from app.repos.provenance_index import (
    InMemoryProvenanceIndex,
    PostgresProvenanceIndex,
    ProvenanceIndex,
)
from app.repos.setting_repo import SettingRepo, SqlSettingRepo
from app.repos.story_repo import InMemoryStoryRepo, PostgresStoryRepo, StoryRepo
from app.repos.theme_repo import SqlThemeRepo, ThemeRepo
from app.security import PromptSecurityManager
from app.services.extractor import ClaudeExtractor, Extractor, MockExtractor

# InMemory singletons (shared state for the lifetime of the process)
_graph_repo = InMemoryGraphRepo()
_story_repo = InMemoryStoryRepo()
_branch_repo = InMemoryBranchRepo()
_prov_index = InMemoryProvenanceIndex()
_mock_extractor = MockExtractor()
_prompt_security_manager = PromptSecurityManager()


# Dependency provider functions (used with FastAPI Depends())

def get_graph_repo() -> GraphRepo:
    if settings.is_mock:
        return _graph_repo
    raise NotImplementedError("Real mode not yet wired, use AMPERSAND_BACKEND_MODE=mock")


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


def get_prompt_security_manager() -> PromptSecurityManager:
    return _prompt_security_manager


def get_beat_repo(session: AsyncSession = Depends(get_db)) -> BeatRepo:
    return SqlBeatRepo(session)


def get_character_repo(session: AsyncSession = Depends(get_db)) -> CharacterRepo:
    if settings.is_mock:
        raise NotImplementedError("CharacterRepo has no mock implementation; use real mode")
    return SqlCharacterRepo(session)


def get_conversation_repo(session: AsyncSession = Depends(get_db)) -> ConversationTurnRepo:
    if settings.is_mock:
        raise NotImplementedError("ConversationTurnRepo has no mock implementation; use real mode")
    return SqlConversationTurnRepo(session)


def get_issue_repo(session: AsyncSession = Depends(get_db)) -> IssueRepo:
    if settings.is_mock:
        raise NotImplementedError("IssueRepo has no mock implementation; use real mode")
    return SqlIssueRepo(session)


def get_project_repo(session: AsyncSession = Depends(get_db)) -> ProjectRepo:
    if settings.is_mock:
        raise NotImplementedError("ProjectRepo has no mock implementation; use real mode")
    return SqlProjectRepo(session)


def get_setting_repo(session: AsyncSession = Depends(get_db)) -> SettingRepo:
    if settings.is_mock:
        raise NotImplementedError("SettingRepo has no mock implementation; use real mode")
    return SqlSettingRepo(session)


def get_theme_repo(session: AsyncSession = Depends(get_db)) -> ThemeRepo:
    if settings.is_mock:
        raise NotImplementedError("ThemeRepo has no mock implementation; use real mode")
    return SqlThemeRepo(session)
