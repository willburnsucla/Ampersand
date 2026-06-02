"""DI wiring for the v2 stack.

get_orchestrator is the composition root for a turn: it builds the repos and
services from one request-scoped session and hands back a ConversationOrchestrator.
The v2 repos are Sql-only, so this path needs a real database; MockExtractorV2 is
used until ClaudeExtractorV2 lands behind the same abc.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repos.beat_repo import SqlBeatRepo
from app.repos.branch_repo import SqlBranchRepo
from app.repos.character_repo import SqlCharacterRepo
from app.repos.conversation_repo import SqlConversationTurnRepo
from app.repos.project_repo import SqlProjectRepo
from app.repos.setting_repo import SqlSettingRepo
from app.repos.theme_repo import SqlThemeRepo
from app.services.consistency_checker import HeuristicConsistencyChecker
from app.services.context_builder import ContextBuilder
from app.services.delta_applier import DeltaApplier
from app.services.extractor_v2 import MockExtractorV2
from app.services.orchestrator import ConversationOrchestrator
from app.services.socratic_prompter import SocraticPrompter


def get_orchestrator(session: AsyncSession = Depends(get_db)) -> ConversationOrchestrator:
    beats = SqlBeatRepo(session)
    characters = SqlCharacterRepo(session)
    themes = SqlThemeRepo(session)
    settings = SqlSettingRepo(session)
    conversations = SqlConversationTurnRepo(session)
    return ConversationOrchestrator(
        projects=SqlProjectRepo(session),
        branches=SqlBranchRepo(session),
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
