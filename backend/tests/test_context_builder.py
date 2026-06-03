"""Integration tests for ContextBuilder against a real Postgres."""
from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.beat_repo import SqlBeatRepo
from app.repos.character_repo import SqlCharacterRepo
from app.repos.conversation_repo import SqlConversationTurnRepo
from app.repos.setting_repo import SqlSettingRepo
from app.repos.theme_repo import SqlThemeRepo
from app.services.context_builder import ContextBuilder


async def _seed(db_session):
    project = ProjectOrm(owner_id="user-1", title="proj")
    db_session.add(project)
    await db_session.flush()
    branch = BranchOrm(project_id=project.id, name="main")
    db_session.add(branch)
    await db_session.flush()
    return project, branch


def _builder(db_session) -> ContextBuilder:
    return ContextBuilder(
        beats=SqlBeatRepo(db_session),
        characters=SqlCharacterRepo(db_session),
        themes=SqlThemeRepo(db_session),
        settings=SqlSettingRepo(db_session),
        conversations=SqlConversationTurnRepo(db_session),
    )


async def test_build_gathers_branch_and_project_state(db_session):
    project, branch = await _seed(db_session)
    await SqlBeatRepo(db_session).create(
        branch_id=branch.id, sequence_index_in_branch=0, logline="b0"
    )
    await SqlCharacterRepo(db_session).create(project_id=project.id, name="Sarah")
    await SqlConversationTurnRepo(db_session).append_turn(
        branch_id=branch.id, role="writer", content="hi"
    )

    ctx = await _builder(db_session).build(
        project_id=project.id, branch_id=branch.id, user_message="what next"
    )

    assert ctx.user_message == "what next"
    assert [b.logline for b in ctx.recent_beats] == ["b0"]
    assert {c.name for c in ctx.characters} == {"Sarah"}
    assert len(ctx.recent_turns) == 1


# an empty branch builds a context with empty collections, not an error
async def test_build_on_empty_branch(db_session):
    project, branch = await _seed(db_session)
    ctx = await _builder(db_session).build(
        project_id=project.id, branch_id=branch.id, user_message="start"
    )
    assert ctx.recent_beats == []
    assert ctx.characters == []
    assert ctx.recent_turns == []
