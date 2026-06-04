"""DI wiring for the v2 stack.

get_orchestrator is the composition root for a turn. It is mode aware: mock mode
wires the orchestrator from process-level InMemory repos (no database), real mode
builds Sql repos from one request-scoped session. The decision is made on whether
a session was provided: get_v2_session yields None in mock mode and a live session
in real mode. The service assembly (context builder, delta applier, checker, mock
extractor, socratic) is identical either way; only the repo backing changes.
MockExtractorV2 stands in until ClaudeExtractorV2 lands behind the same abc.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.db import AsyncSessionLocal
from app.repos.beat_repo import InMemoryBeatRepo, SqlBeatRepo
from app.repos.branch_repo import InMemoryBranchRepo, SqlBranchRepo
from app.repos.character_repo import InMemoryCharacterRepo, SqlCharacterRepo
from app.repos.conversation_repo import InMemoryConversationTurnRepo, SqlConversationTurnRepo
from app.repos.project_repo import InMemoryProjectRepo, SqlProjectRepo
from app.repos.setting_repo import InMemorySettingRepo, SqlSettingRepo
from app.repos.theme_repo import InMemoryThemeRepo, SqlThemeRepo
from app.services.consistency_checker import HeuristicConsistencyChecker
from app.services.context_builder import ContextBuilder
from app.services.delta_applier import DeltaApplier
from app.services.extractor_v2 import MockExtractorV2
from app.services.orchestrator import ConversationOrchestrator
from app.services.socratic_prompter import SocraticPrompter

# Process-level InMemory repos for mock mode. Shared across requests for the life
# of the server, the same pattern as the v1 singletons in dependencies.py, so a
# project/branch/beat created on one turn is visible to the next. There is no
# issue-repo singleton: the orchestrator returns issues but does not persist them
# on a turn, so nothing in the turn path needs one.
_projects = InMemoryProjectRepo()
_branches = InMemoryBranchRepo()
_beats = InMemoryBeatRepo()
_characters = InMemoryCharacterRepo()
_themes = InMemoryThemeRepo()
_settings = InMemorySettingRepo()
_conversations = InMemoryConversationTurnRepo()


async def get_v2_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield a db session in real mode, or None in mock mode (no connection opened).

    Mirrors get_db's commit/rollback lifecycle for the real branch. Mock mode never
    touches the database, which is what lets the v2 turn run under make dev-mock.
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


def _assemble(
    *, projects, branches, beats, characters, themes, settings, conversations
) -> ConversationOrchestrator:
    return ConversationOrchestrator(
        projects=projects,
        branches=branches,
        conversations=conversations,
        context_builder=ContextBuilder(
            beats=beats, characters=characters, themes=themes,
            settings=settings, conversations=conversations,
        ),
        extractor=MockExtractorV2(),
        delta_applier=DeltaApplier(
            beats=beats, characters=characters, themes=themes, settings=settings
        ),
        checker=HeuristicConsistencyChecker(beats),
        socratic=SocraticPrompter(),
    )


def get_orchestrator(
    session: AsyncSession | None = Depends(get_v2_session),
) -> ConversationOrchestrator:
    # no session means mock mode: wire the process-level InMemory repos. a session
    # (real mode, or the sql router test that overrides get_v2_session) wires sql.
    if session is None:
        return _assemble(
            projects=_projects,
            branches=_branches,
            beats=_beats,
            characters=_characters,
            themes=_themes,
            settings=_settings,
            conversations=_conversations,
        )
    return _assemble(
        projects=SqlProjectRepo(session),
        branches=SqlBranchRepo(session),
        beats=SqlBeatRepo(session),
        characters=SqlCharacterRepo(session),
        themes=SqlThemeRepo(session),
        settings=SqlSettingRepo(session),
        conversations=SqlConversationTurnRepo(session),
    )
