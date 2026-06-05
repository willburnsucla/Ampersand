"""DI wiring for the v2 stack.

The mode-vs-backing decision lives in exactly one place, the _repo helper: with no
session it hands back the process-level InMemory repo (mock mode, no database), with a
session it builds a fresh Sql repo on it (real mode). The seam that decides which is
get_v2_session, yielding None in mock mode and a live session in real mode. The per-repo
providers (used by the read endpoints in router_v2) and get_orchestrator (the turn) both
source their repos through that one decision, so the whole v2 surface runs under make
dev-mock with no postgres. The extractor is a separate axis: get_extractor wires
MockExtractorV2 or GeminiExtractorV2 by extractor_backend.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.db import AsyncSessionLocal
from app.repos.beat_repo import BeatRepo, InMemoryBeatRepo, SqlBeatRepo
from app.repos.branch_repo import BranchRepo, InMemoryBranchRepo, SqlBranchRepo
from app.repos.character_repo import CharacterRepo, InMemoryCharacterRepo, SqlCharacterRepo
from app.repos.conversation_repo import (
    ConversationTurnRepo,
    InMemoryConversationTurnRepo,
    SqlConversationTurnRepo,
)
from app.repos.issue_repo import InMemoryIssueRepo, IssueRepo, SqlIssueRepo
from app.repos.project_repo import InMemoryProjectRepo, ProjectRepo, SqlProjectRepo
from app.repos.setting_repo import InMemorySettingRepo, SettingRepo, SqlSettingRepo
from app.repos.theme_repo import InMemoryThemeRepo, SqlThemeRepo, ThemeRepo
from app.services.consistency_checker import HeuristicConsistencyChecker
from app.services.context_builder import ContextBuilder
from app.services.delta_applier import DeltaApplier
from app.services.extractor_v2 import ExtractorV2, GeminiExtractorV2, MockExtractorV2
from app.services.orchestrator import ConversationOrchestrator
from app.services.socratic_prompter import SocraticPrompter

# Process-level InMemory repos for mock mode, shared across requests for the life of the
# server (the same pattern as the v1 singletons in dependencies.py), so a project or
# branch created on one request is visible to the next. The issue singleton is here for
# the list_issues read endpoint; the turn path never persists issues.
_projects = InMemoryProjectRepo()
_branches = InMemoryBranchRepo()
_beats = InMemoryBeatRepo()
_characters = InMemoryCharacterRepo()
_themes = InMemoryThemeRepo()
_settings = InMemorySettingRepo()
_issues = InMemoryIssueRepo()
_conversations = InMemoryConversationTurnRepo()


async def get_v2_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield a db session in real mode, or None in mock mode (no connection opened).

    Mirrors get_db's commit/rollback lifecycle for the real branch. Mock mode never
    touches the database, which is what lets the v2 surface run under make dev-mock.
    """
    if app_settings.is_mock:
        yield None
        return
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _repo(session: AsyncSession | None, mock_repo, sql_cls):
    # the single home of the mode->backing decision: the process-level mock repo when
    # there is no session, a fresh Sql repo on the session otherwise.
    return mock_repo if session is None else sql_cls(session)


# Per-repo providers for the read endpoints in router_v2. Each is a thin delegator to
# _repo, so the mock-vs-real decision is not restated here.

def get_project_repo(session: AsyncSession | None = Depends(get_v2_session)) -> ProjectRepo:
    return _repo(session, _projects, SqlProjectRepo)


def get_branch_repo_v2(session: AsyncSession | None = Depends(get_v2_session)) -> BranchRepo:
    return _repo(session, _branches, SqlBranchRepo)


def get_beat_repo(session: AsyncSession | None = Depends(get_v2_session)) -> BeatRepo:
    return _repo(session, _beats, SqlBeatRepo)


def get_character_repo(session: AsyncSession | None = Depends(get_v2_session)) -> CharacterRepo:
    return _repo(session, _characters, SqlCharacterRepo)


def get_theme_repo(session: AsyncSession | None = Depends(get_v2_session)) -> ThemeRepo:
    return _repo(session, _themes, SqlThemeRepo)


def get_setting_repo(session: AsyncSession | None = Depends(get_v2_session)) -> SettingRepo:
    return _repo(session, _settings, SqlSettingRepo)


def get_issue_repo(session: AsyncSession | None = Depends(get_v2_session)) -> IssueRepo:
    return _repo(session, _issues, SqlIssueRepo)


def get_conversation_repo(
    session: AsyncSession | None = Depends(get_v2_session),
) -> ConversationTurnRepo:
    return _repo(session, _conversations, SqlConversationTurnRepo)


def get_extractor() -> ExtractorV2:
    # the extractor is its own axis, independent of whether repos are mock or sql, so you
    # can run real extraction under make dev-mock with no database.
    if app_settings.extractor_backend == "gemini":
        return GeminiExtractorV2()
    return MockExtractorV2()


def get_orchestrator(
    projects: ProjectRepo = Depends(get_project_repo),
    branches: BranchRepo = Depends(get_branch_repo_v2),
    beats: BeatRepo = Depends(get_beat_repo),
    characters: CharacterRepo = Depends(get_character_repo),
    themes: ThemeRepo = Depends(get_theme_repo),
    settings: SettingRepo = Depends(get_setting_repo),
    conversations: ConversationTurnRepo = Depends(get_conversation_repo),
    extractor: ExtractorV2 = Depends(get_extractor),
) -> ConversationOrchestrator:
    # pure assembly: the repos arrive already mode-resolved through the providers, so
    # there is no mock-vs-real branching here.
    return ConversationOrchestrator(
        projects=projects,
        branches=branches,
        conversations=conversations,
        context_builder=ContextBuilder(
            beats=beats, characters=characters, themes=themes,
            settings=settings, conversations=conversations,
        ),
        extractor=extractor,
        delta_applier=DeltaApplier(
            beats=beats, characters=characters, themes=themes, settings=settings
        ),
        checker=HeuristicConsistencyChecker(beats),
        socratic=SocraticPrompter(),
    )
