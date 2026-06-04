"""Black-box repo contract, run against both the Sql and InMemory v2 repos.

The same behavioral spec is parametrized over ["sql", "memory"] so the two impls
must agree. The `repos` fixture hands back a bundle of all eight repos wired to
one backend: `sql` builds Sql*Repo on the rolled-back test session, `memory`
builds fresh InMemory*Repo instances per test.

Two divergences are deliberate and asserted loosely, not hidden:
  - duplicate sequence / bad affect: Sql raises IntegrityError, InMemory raises
    a ValueError/ValidationError; both subclass Exception, so we assert
    pytest.raises(Exception).
  - cross-store tenancy: Sql's upsert_overlay also checks the branch lives in the
    project (a sibling-table query). InMemory holds no sibling store, so it checks
    only the entity-in-project and leans on the orchestrator's _authorize. The
    contract asserts the entity-in-project rejection, which both share.

This suite uses the testcontainer for its `sql` params (and provisions the
session for `memory` params too, unused). The no-database proof lives in
test_router_v2_mock.py, which drives the turn endpoint with no session at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from app.domain.branch_state_machine import BranchEvent, InvalidTransitionError
from app.repos.beat_repo import InMemoryBeatRepo, SqlBeatRepo
from app.repos.branch_repo import InMemoryBranchRepo, SqlBranchRepo
from app.repos.character_repo import InMemoryCharacterRepo, SqlCharacterRepo
from app.repos.conversation_repo import InMemoryConversationTurnRepo, SqlConversationTurnRepo
from app.repos.issue_repo import InMemoryIssueRepo, SqlIssueRepo
from app.repos.project_repo import InMemoryProjectRepo, SqlProjectRepo
from app.repos.setting_repo import InMemorySettingRepo, SqlSettingRepo
from app.repos.theme_repo import InMemoryThemeRepo, SqlThemeRepo


@dataclass
class Repos:
    projects: object
    branches: object
    beats: object
    characters: object
    themes: object
    settings: object
    issues: object
    conversations: object


@pytest_asyncio.fixture(params=["sql", "memory"])
async def repos(request, db_session) -> Repos:
    if request.param == "sql":
        s = db_session
        return Repos(
            projects=SqlProjectRepo(s),
            branches=SqlBranchRepo(s),
            beats=SqlBeatRepo(s),
            characters=SqlCharacterRepo(s),
            themes=SqlThemeRepo(s),
            settings=SqlSettingRepo(s),
            issues=SqlIssueRepo(s),
            conversations=SqlConversationTurnRepo(s),
        )
    return Repos(
        projects=InMemoryProjectRepo(),
        branches=InMemoryBranchRepo(),
        beats=InMemoryBeatRepo(),
        characters=InMemoryCharacterRepo(),
        themes=InMemoryThemeRepo(),
        settings=InMemorySettingRepo(),
        issues=InMemoryIssueRepo(),
        conversations=InMemoryConversationTurnRepo(),
    )


# ── helpers ───────────────────────────────────────────────────────────────────


async def _project(repos: Repos, *, owner: str = "owner-1", title: str = "a story") -> object:
    return await repos.projects.create(title=title, owner_id=owner)


async def _branch(repos: Repos, project, *, name: str = "main") -> object:
    return await repos.branches.create(project_id=project.id, name=name)


_ENTITY_ID_KW = {"characters": "character_id", "themes": "theme_id", "settings": "setting_id"}


def _entity(repos: Repos, kind: str):
    """Return (repo, id_kwarg_name) for one of the three overlayable entities."""
    return getattr(repos, kind), _ENTITY_ID_KW[kind]


ENTITY_KINDS = ["characters", "themes", "settings"]


# ── Project ─────────────────────────────────────────────────────────────────--


async def test_project_create_get_roundtrip(repos):
    created = await repos.projects.create(title="my story", owner_id="owner-1")
    assert created.title == "my story"
    assert created.owner_id == "owner-1"

    fetched = await repos.projects.get(created.id, owner_id="owner-1")
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "my story"


async def test_project_get_wrong_owner_returns_none(repos):
    created = await repos.projects.create(title="mine", owner_id="owner-1")
    assert await repos.projects.get(created.id, owner_id="owner-2") is None


async def test_project_list_scoped_to_owner(repos):
    await repos.projects.create(title="p1", owner_id="owner-1")
    await repos.projects.create(title="p2", owner_id="owner-1")
    await repos.projects.create(title="other", owner_id="owner-2")

    mine = await repos.projects.list(owner_id="owner-1")
    assert {p.title for p in mine} == {"p1", "p2"}
    assert await repos.projects.list(owner_id="nobody") == []


async def test_project_set_primary_branch(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)

    updated = await repos.projects.set_primary_branch(
        project.id, branch.id, owner_id=project.owner_id
    )
    assert updated.primary_branch_id == branch.id


async def test_project_set_primary_branch_missing_raises(repos):
    with pytest.raises(ValueError):
        await repos.projects.set_primary_branch(uuid4(), uuid4(), owner_id="owner-1")


# ── Branch ──────────────────────────────────────────────────────────────────--


async def test_branch_create_get_roundtrip(repos):
    project = await _project(repos)
    created = await repos.branches.create(project_id=project.id, name="alt")

    assert created.state == "active"
    fetched = await repos.branches.get(created.id, project_id=project.id)
    assert fetched is not None
    assert fetched.name == "alt"


async def test_branch_get_wrong_project_returns_none(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    assert await repos.branches.get(branch.id, project_id=uuid4()) is None


async def test_branch_list_scoped_to_project(repos):
    p1 = await _project(repos, owner="owner-1", title="one")
    p2 = await _project(repos, owner="owner-1", title="two")
    await repos.branches.create(project_id=p1.id, name="a")
    await repos.branches.create(project_id=p1.id, name="b")
    await repos.branches.create(project_id=p2.id, name="c")

    listed = await repos.branches.list(project_id=p1.id)
    assert {b.name for b in listed} == {"a", "b"}


async def test_branch_transition_legal(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)

    dormant = await repos.branches.transition(
        branch.id, BranchEvent.SWITCH_TO_DORMANT, project_id=project.id
    )
    assert dormant.state == "dormant"


async def test_branch_transition_illegal_raises(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)  # starts active

    with pytest.raises(InvalidTransitionError):
        # REVIVE is only legal from graveyard, never from active
        await repos.branches.transition(branch.id, BranchEvent.REVIVE, project_id=project.id)


async def test_branch_create_fork_caps_at_three(repos):
    project = await _project(repos)
    parent = await _branch(repos, project)
    fork_beat = await repos.beats.create(
        branch_id=parent.id, sequence_index_in_branch=1, logline="the split"
    )

    for i in range(3):
        await repos.branches.create_fork(
            project_id=project.id,
            parent_branch_id=parent.id,
            created_from_beat_id=fork_beat.id,
            name=f"fork-{i}",
        )

    with pytest.raises(ValueError):
        await repos.branches.create_fork(
            project_id=project.id,
            parent_branch_id=parent.id,
            created_from_beat_id=fork_beat.id,
            name="fork-4",
        )


async def test_branch_create_fork_unknown_parent_raises(repos):
    project = await _project(repos)
    with pytest.raises(ValueError):
        await repos.branches.create_fork(
            project_id=project.id,
            parent_branch_id=uuid4(),
            created_from_beat_id=uuid4(),
        )


# ── Beat ────────────────────────────────────────────────────────────────────--


async def test_beat_create_get_roundtrip(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    created = await repos.beats.create(
        branch_id=branch.id,
        sequence_index_in_branch=1,
        logline="the detective finds a body",
        content={"scene": "pier"},
        valence=0.2,
        arousal=0.7,
    )
    assert created.logline == "the detective finds a body"
    assert created.status == "proposed"

    fetched = await repos.beats.get(created.id, branch_id=branch.id)
    assert fetched is not None
    assert fetched.content == {"scene": "pier"}
    assert fetched.valence == 0.2


async def test_beat_get_wrong_branch_returns_none(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    created = await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="x")
    assert await repos.beats.get(created.id, branch_id=uuid4()) is None


async def test_beat_list_orders_by_sequence_index(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=3, logline="third")
    await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="first")
    await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=2, logline="second")

    listed = await repos.beats.list(branch_id=branch.id)
    assert [b.logline for b in listed] == ["first", "second", "third"]


async def test_beat_duplicate_sequence_raises(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="first")

    with pytest.raises(Exception):  # noqa: B017 sql and memory raise different types
        await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="dup")


async def test_beat_affect_must_be_atomic(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)

    with pytest.raises(Exception):  # noqa: B017 sql and memory raise different types
        await repos.beats.create(
            branch_id=branch.id,
            sequence_index_in_branch=1,
            logline="half",
            valence=0.5,
        )


async def test_beat_set_status(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    created = await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="x")
    assert created.status == "proposed"

    updated = await repos.beats.set_status(created.id, "committed", branch_id=branch.id)
    assert updated.status == "committed"


async def test_beat_set_status_missing_raises(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    with pytest.raises(ValueError):
        await repos.beats.set_status(uuid4(), "committed", branch_id=branch.id)


# ── Character / Theme / Setting (the three overlayable entities) ──────────────-


@pytest.mark.parametrize("kind", ENTITY_KINDS)
async def test_entity_create_get_roundtrip(repos, kind):
    repo, _ = _entity(repos, kind)
    project = await _project(repos)
    created = await repo.create(
        project_id=project.id, name="Maya", base_properties={"role": "lead"}
    )

    assert created.name == "Maya"
    fetched = await repo.get(created.id, project_id=project.id)
    assert fetched is not None
    assert fetched.base_properties == {"role": "lead"}


@pytest.mark.parametrize("kind", ENTITY_KINDS)
async def test_entity_get_wrong_project_returns_none(repos, kind):
    repo, _ = _entity(repos, kind)
    project = await _project(repos)
    created = await repo.create(project_id=project.id, name="Maya")
    assert await repo.get(created.id, project_id=uuid4()) is None


@pytest.mark.parametrize("kind", ENTITY_KINDS)
async def test_entity_view_merges_overlay_over_base(repos, kind):
    repo, id_kw = _entity(repos, kind)
    project = await _project(repos)
    branch = await _branch(repos, project)
    entity = await repo.create(
        project_id=project.id,
        name="Maya",
        base_properties={"hair": "black", "age": 30},
    )

    # no overlay yet: view is the base
    base_view = await repo.get_view(entity.id, branch.id, project_id=project.id)
    assert base_view is not None
    assert base_view.properties == {"hair": "black", "age": 30}
    assert base_view.resolved_in_branch == branch.id
    assert base_view.id == entity.id

    # overlay wins on the keys it sets, base shows through elsewhere
    await repo.upsert_overlay(
        branch_id=branch.id,
        project_id=project.id,
        overlay_properties={"hair": "white"},
        **{id_kw: entity.id},
    )
    merged = await repo.get_view(entity.id, branch.id, project_id=project.id)
    assert merged.properties == {"hair": "white", "age": 30}


@pytest.mark.parametrize("kind", ENTITY_KINDS)
async def test_entity_view_unknown_returns_none(repos, kind):
    repo, _ = _entity(repos, kind)
    project = await _project(repos)
    branch = await _branch(repos, project)
    assert await repo.get_view(uuid4(), branch.id, project_id=project.id) is None


@pytest.mark.parametrize("kind", ENTITY_KINDS)
async def test_entity_upsert_overlay_updates_in_place(repos, kind):
    repo, id_kw = _entity(repos, kind)
    project = await _project(repos)
    branch = await _branch(repos, project)
    entity = await repo.create(project_id=project.id, name="Maya", base_properties={"k": "base"})

    await repo.upsert_overlay(
        branch_id=branch.id,
        project_id=project.id,
        overlay_properties={"k": "first"},
        **{id_kw: entity.id},
    )
    await repo.upsert_overlay(
        branch_id=branch.id,
        project_id=project.id,
        overlay_properties={"k": "second"},
        **{id_kw: entity.id},
    )
    view = await repo.get_view(entity.id, branch.id, project_id=project.id)
    assert view.properties == {"k": "second"}


@pytest.mark.parametrize("kind", ENTITY_KINDS)
async def test_entity_upsert_overlay_unknown_entity_raises(repos, kind):
    repo, id_kw = _entity(repos, kind)
    project = await _project(repos)
    branch = await _branch(repos, project)
    with pytest.raises(ValueError):
        await repo.upsert_overlay(
            branch_id=branch.id,
            project_id=project.id,
            overlay_properties={"k": "v"},
            **{id_kw: uuid4()},
        )


@pytest.mark.parametrize("kind", ENTITY_KINDS)
async def test_entity_link_to_beat_is_idempotent(repos, kind):
    repo, id_kw = _entity(repos, kind)
    project = await _project(repos)
    branch = await _branch(repos, project)
    beat = await repos.beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="x")
    entity = await repo.create(project_id=project.id, name="Maya")

    await repo.link_to_beat(beat_id=beat.id, **{id_kw: entity.id})
    await repo.link_to_beat(beat_id=beat.id, **{id_kw: entity.id})  # second is a no-op

    linked = await repo.list_for_beat(beat.id, project_id=project.id)
    assert [e.id for e in linked] == [entity.id]


# ── Issue ───────────────────────────────────────────────────────────────────--


async def test_issue_create_get_roundtrip(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    created = await repos.issues.create(
        branch_id=branch.id,
        type="timeline_gap",
        description="beats 2 and 4 but no 3",
    )
    assert created.status == "open"
    assert created.resolved_at is None

    fetched = await repos.issues.get(created.id, branch_id=branch.id)
    assert fetched is not None
    assert fetched.type == "timeline_gap"


async def test_issue_list_scoped_to_branch(repos):
    project = await _project(repos)
    b1 = await _branch(repos, project, name="b1")
    b2 = await _branch(repos, project, name="b2")
    await repos.issues.create(branch_id=b1.id, type="contradiction", description="one")
    await repos.issues.create(branch_id=b2.id, type="pacing_anomaly", description="two")

    listed = await repos.issues.list(branch_id=b1.id)
    assert [i.description for i in listed] == ["one"]


async def test_issue_set_status_resolved_stamps_resolved_at(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    created = await repos.issues.create(branch_id=branch.id, type="contradiction", description="x")

    resolved = await repos.issues.set_status(created.id, "resolved", branch_id=branch.id)
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None


async def test_issue_set_status_missing_raises(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    with pytest.raises(ValueError):
        await repos.issues.set_status(uuid4(), "resolved", branch_id=branch.id)


# ── Conversation turns ────────────────────────────────────────────────────────


async def test_conversation_append_get_roundtrip(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    created = await repos.conversations.append_turn(
        branch_id=branch.id,
        role="writer",
        content="the detective enters",
    )
    assert created.role == "writer"

    fetched = await repos.conversations.get_turn(created.id)
    assert fetched is not None
    assert fetched.id == created.id


async def test_conversation_list_scoped_to_branch(repos):
    project = await _project(repos)
    b1 = await _branch(repos, project, name="b1")
    b2 = await _branch(repos, project, name="b2")
    await repos.conversations.append_turn(branch_id=b1.id, role="writer", content="A1")
    await repos.conversations.append_turn(branch_id=b2.id, role="writer", content="B1")

    listed = await repos.conversations.list_turns(b1.id)
    assert {t.content for t in listed} == {"A1"}


async def test_conversation_list_returns_all_appended(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    for i in range(3):
        await repos.conversations.append_turn(branch_id=branch.id, role="writer", content=f"m{i}")

    listed = await repos.conversations.list_turns(branch.id)
    assert {t.content for t in listed} == {"m0", "m1", "m2"}


async def test_conversation_list_respects_limit(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    for i in range(5):
        await repos.conversations.append_turn(branch_id=branch.id, role="writer", content=f"m{i}")

    assert len(await repos.conversations.list_turns(branch.id, limit=3)) == 3


async def test_conversation_before_filter(repos):
    project = await _project(repos)
    branch = await _branch(repos, project)
    await repos.conversations.append_turn(branch_id=branch.id, role="writer", content="a")
    await repos.conversations.append_turn(branch_id=branch.id, role="writer", content="b")

    far_future = datetime(2999, 1, 1, tzinfo=UTC)
    far_past = datetime(2000, 1, 1, tzinfo=UTC)
    assert len(await repos.conversations.list_turns(branch.id, before=far_future)) == 2
    assert await repos.conversations.list_turns(branch.id, before=far_past) == []
