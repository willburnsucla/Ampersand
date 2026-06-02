"""Integration tests for ConversationOrchestrator against a real Postgres.

Wires the real repos, the real services, and MockExtractorV2 so one turn runs
end to end through the whole v2 stack.
"""
import pytest

from app.domain.models_v2 import TurnRequestV2
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
from app.services.orchestrator import ConversationOrchestrator, TurnAuthorizationError
from app.services.socratic_prompter import SocraticPrompter


def _orchestrator(db_session) -> ConversationOrchestrator:
    beats = SqlBeatRepo(db_session)
    characters = SqlCharacterRepo(db_session)
    themes = SqlThemeRepo(db_session)
    settings = SqlSettingRepo(db_session)
    conversations = SqlConversationTurnRepo(db_session)
    return ConversationOrchestrator(
        projects=SqlProjectRepo(db_session),
        branches=SqlBranchRepo(db_session),
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


async def _project_and_branch(db_session, *, owner: str = "user-1"):
    project = await SqlProjectRepo(db_session).create(title="proj", owner_id=owner)
    branch = await SqlBranchRepo(db_session).create(project_id=project.id, name="main")
    return project, branch


# a full turn writes a proposed beat, links the entity, and logs both turns
async def test_turn_writes_a_beat_and_links_entities(db_session):
    project, branch = await _project_and_branch(db_session)
    req = TurnRequestV2(
        project_id=project.id, branch_id=branch.id,
        content="the detective enters the forest",
    )

    result = await _orchestrator(db_session).handle_turn(req, owner_id="user-1")

    assert result.beat is not None
    assert result.beat.status == "proposed"
    assert result.reply

    chars = await SqlCharacterRepo(db_session).list_for_beat(result.beat.id, project_id=project.id)
    assert {c.name for c in chars} == {"Maya"}

    turns = await SqlConversationTurnRepo(db_session).list_turns(branch.id)
    assert {t.role for t in turns} == {"writer", "assistant"}


# a thin message gets a clarifying question and writes no beat
async def test_short_message_asks_instead_of_writing(db_session):
    project, branch = await _project_and_branch(db_session)
    req = TurnRequestV2(project_id=project.id, branch_id=branch.id, content="she runs")

    result = await _orchestrator(db_session).handle_turn(req, owner_id="user-1")

    assert result.beat is None
    assert result.reply.endswith("?")
    assert await SqlBeatRepo(db_session).list(branch_id=branch.id) == []


# a writer cannot post a turn to a project they do not own
async def test_turn_rejects_wrong_owner(db_session):
    project, branch = await _project_and_branch(db_session, owner="user-1")
    req = TurnRequestV2(
        project_id=project.id, branch_id=branch.id,
        content="the detective enters the forest",
    )
    with pytest.raises(TurnAuthorizationError):
        await _orchestrator(db_session).handle_turn(req, owner_id="intruder")


# naming an owned project with a branch from another project is rejected
async def test_turn_rejects_branch_from_another_project(db_session):
    project_a = await SqlProjectRepo(db_session).create(title="a", owner_id="user-1")
    project_b = await SqlProjectRepo(db_session).create(title="b", owner_id="user-1")
    branch_b = await SqlBranchRepo(db_session).create(project_id=project_b.id, name="main")
    req = TurnRequestV2(
        project_id=project_a.id, branch_id=branch_b.id,
        content="the detective enters the forest",
    )
    with pytest.raises(TurnAuthorizationError):
        await _orchestrator(db_session).handle_turn(req, owner_id="user-1")
