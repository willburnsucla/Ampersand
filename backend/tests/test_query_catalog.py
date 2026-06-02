"""Integration tests for QueryCatalog against a real Postgres (testcontainers)."""
import uuid

import pytest
from pydantic import ValidationError

from app.domain.orm_v2 import (
    BeatCharacterOrm,
    BeatSettingOrm,
    BeatThemeOrm,
    BranchOrm,
    IssueOrm,
    ProjectOrm,
)
from app.repos.beat_repo import SqlBeatRepo
from app.repos.character_repo import SqlCharacterRepo
from app.repos.issue_repo import SqlIssueRepo
from app.repos.setting_repo import SqlSettingRepo
from app.repos.theme_repo import SqlThemeRepo
from app.services.query_catalog import QueryCatalog


async def _seed(db_session, *, owner: str = "user-1", title: str = "proj"):
    project = ProjectOrm(owner_id=owner, title=title)
    db_session.add(project)
    await db_session.flush()
    branch = BranchOrm(project_id=project.id, name="main")
    db_session.add(branch)
    await db_session.flush()
    return project, branch


def _catalog(db_session, project_id, branch_id) -> QueryCatalog:
    return QueryCatalog(
        project_id=project_id,
        branch_id=branch_id,
        beats=SqlBeatRepo(db_session),
        characters=SqlCharacterRepo(db_session),
        themes=SqlThemeRepo(db_session),
        settings=SqlSettingRepo(db_session),
        issues=SqlIssueRepo(db_session),
    )


async def test_get_beats_in_branch_orders_and_filters(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    await beats.create(branch_id=branch.id, sequence_index_in_branch=3, logline="b3")
    await beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="b1")
    await beats.create(branch_id=branch.id, sequence_index_in_branch=2, logline="b2")
    cat = _catalog(db_session, project.id, branch.id)

    everything = await cat.get_beats_in_branch()
    assert [b.sequence_index_in_branch for b in everything] == [1, 2, 3]

    window = await cat.get_beats_in_branch(start=2, end=2)
    assert [b.logline for b in window] == ["b2"]


async def test_get_beat_roundtrip_and_missing(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    b = await beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="b1")
    cat = _catalog(db_session, project.id, branch.id)

    got = await cat.get_beat(b.id)
    assert got is not None and got.id == b.id
    assert await cat.get_beat(uuid.uuid4()) is None


async def test_list_entities(db_session):
    project, branch = await _seed(db_session)
    await SqlCharacterRepo(db_session).create(project_id=project.id, name="Sarah")
    await SqlThemeRepo(db_session).create(project_id=project.id, name="Justice")
    await SqlSettingRepo(db_session).create(project_id=project.id, name="the pier")
    cat = _catalog(db_session, project.id, branch.id)

    assert {c.name for c in await cat.list_characters()} == {"Sarah"}
    assert {t.name for t in await cat.list_themes()} == {"Justice"}
    assert {s.name for s in await cat.list_settings()} == {"the pier"}


async def test_get_character_view_merges_overlay(db_session):
    project, branch = await _seed(db_session)
    chars = SqlCharacterRepo(db_session)
    sarah = await chars.create(project_id=project.id, name="Sarah", base_properties={"age": 30})
    await chars.upsert_overlay(
        character_id=sarah.id, branch_id=branch.id, project_id=project.id,
        overlay_properties={"age": 45},
    )
    cat = _catalog(db_session, project.id, branch.id)

    view = await cat.get_character_view(sarah.id)
    assert view is not None
    assert view.properties == {"age": 45}
    assert view.resolved_in_branch == branch.id


async def test_list_issues_filters_by_status(db_session):
    project, branch = await _seed(db_session)
    db_session.add(IssueOrm(branch_id=branch.id, type="contradiction", description="open one", status="open"))
    db_session.add(IssueOrm(branch_id=branch.id, type="timeline_gap", description="done one", status="resolved"))
    await db_session.flush()
    cat = _catalog(db_session, project.id, branch.id)

    assert len(await cat.list_issues()) == 2
    open_only = await cat.list_issues(status="open")
    assert [i.description for i in open_only] == ["open one"]


async def test_get_beat_entities_bundles_links(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    chars = SqlCharacterRepo(db_session)
    themes = SqlThemeRepo(db_session)
    settings = SqlSettingRepo(db_session)
    beat = await beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="b1")
    sarah = await chars.create(project_id=project.id, name="Sarah")
    justice = await themes.create(project_id=project.id, name="Justice")
    pier = await settings.create(project_id=project.id, name="the pier")
    db_session.add(BeatCharacterOrm(beat_id=beat.id, character_id=sarah.id))
    db_session.add(BeatThemeOrm(beat_id=beat.id, theme_id=justice.id))
    db_session.add(BeatSettingOrm(beat_id=beat.id, setting_id=pier.id))
    await db_session.flush()
    cat = _catalog(db_session, project.id, branch.id)

    bundle = await cat.get_beat_entities(beat.id)
    assert {c.name for c in bundle.characters} == {"Sarah"}
    assert {t.name for t in bundle.themes} == {"Justice"}
    assert {s.name for s in bundle.settings} == {"the pier"}


# the catalog is constructed with a fixed project + branch, so it cannot reach another tenant
async def test_catalog_is_scoped_to_its_tenant(db_session):
    proj_a, branch_a = await _seed(db_session, title="A")
    proj_b, branch_b = await _seed(db_session, title="B")
    sarah = await SqlCharacterRepo(db_session).create(project_id=proj_a.id, name="Sarah")

    cat_b = _catalog(db_session, proj_b.id, branch_b.id)
    assert await cat_b.list_characters() == []
    assert await cat_b.get_character_view(sarah.id) is None


async def test_dispatch_routes_validates_and_coerces(db_session):
    project, branch = await _seed(db_session)
    b = await SqlBeatRepo(db_session).create(
        branch_id=branch.id, sequence_index_in_branch=1, logline="b1"
    )
    cat = _catalog(db_session, project.id, branch.id)

    # the LLM sends ids as JSON strings; the arg model coerces to UUID
    got = await cat.dispatch("get_beat", {"beat_id": str(b.id)})
    assert got is not None and got.id == b.id

    # a no-arg tool dispatches with an empty dict (or None)
    assert await cat.dispatch("list_characters", {}) == []
    assert await cat.dispatch("list_characters") == []

    # unknown tool name is a hard error
    with pytest.raises(ValueError):
        await cat.dispatch("does_not_exist", {})

    # missing a required arg fails validation, not silently
    with pytest.raises(ValidationError):
        await cat.dispatch("get_beat", {})


# ── analytical wave: find_logic_error, scan_branch, classify_arc, framework_anomalies ──

async def test_find_logic_error_flags_a_gap(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    await beats.create(branch_id=branch.id, sequence_index_in_branch=0, logline="b0")
    gap = await beats.create(branch_id=branch.id, sequence_index_in_branch=5, logline="b5")
    cat = _catalog(db_session, project.id, branch.id)

    issues = await cat.find_logic_error(gap.id)
    assert any(i.type == "timeline_gap" for i in issues)


async def test_find_logic_error_clean_beat_is_empty(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    await beats.create(branch_id=branch.id, sequence_index_in_branch=0, logline="b0")
    b1 = await beats.create(branch_id=branch.id, sequence_index_in_branch=1, logline="b1")
    cat = _catalog(db_session, project.id, branch.id)

    assert await cat.find_logic_error(b1.id) == []


async def test_find_logic_error_missing_beat_is_empty(db_session):
    project, branch = await _seed(db_session)
    cat = _catalog(db_session, project.id, branch.id)
    assert await cat.find_logic_error(uuid.uuid4()) == []


async def test_scan_branch_reports_pacing_anomaly(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    for i in range(6):
        await beats.create(
            branch_id=branch.id, sequence_index_in_branch=i, logline=f"b{i}",
            valence=0.1 * i, arousal=0.5,
        )
    cat = _catalog(db_session, project.id, branch.id)

    issues = await cat.scan_branch()
    assert any(i.type == "pacing_anomaly" for i in issues)


async def test_classify_arc_returns_best_fit(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    # man-in-hole: high start, low crisis, high end
    spec = [(0, 0.8, "tp1"), (1, 0.6, None), (2, 0.5, "tp3"), (3, 0.1, "tp4"), (4, 0.8, "tp5")]
    for seq, val, tp in spec:
        await beats.create(
            branch_id=branch.id, sequence_index_in_branch=seq,
            logline=f"b{seq}", valence=val, arousal=0.5, turning_point=tp,
        )
    cat = _catalog(db_session, project.id, branch.id)

    result = await cat.classify_arc()
    assert result.framework == "vonnegut"
    assert result.arc == "man_in_hole"


async def test_framework_anomalies_by_name(db_session):
    project, branch = await _seed(db_session)
    beats = SqlBeatRepo(db_session)
    for i in range(6):
        await beats.create(
            branch_id=branch.id, sequence_index_in_branch=i, logline=f"b{i}",
            valence=0.1 * i, arousal=0.5,
        )
    cat = _catalog(db_session, project.id, branch.id)

    anomalies = await cat.framework_anomalies("vonnegut")
    assert any(a.kind == "arc" for a in anomalies)

    # an unknown framework name is a hard error, not a silent empty list
    with pytest.raises(ValueError):
        await cat.framework_anomalies("aristotle")


async def test_dispatch_reaches_analytical_tools(db_session):
    project, branch = await _seed(db_session)
    b = await SqlBeatRepo(db_session).create(
        branch_id=branch.id, sequence_index_in_branch=0, logline="b0"
    )
    cat = _catalog(db_session, project.id, branch.id)

    # find_logic_error via dispatch, with a JSON-string beat id the model coerces
    assert await cat.dispatch("find_logic_error", {"beat_id": str(b.id)}) == []
    assert isinstance(await cat.dispatch("scan_branch", {}), list)
    arc = await cat.dispatch("classify_arc", {})
    assert arc.framework == "vonnegut"


def test_tool_specs_cover_all_tools():
    # tool_specs is pure, repos are unused here
    cat = QueryCatalog(
        project_id=uuid.uuid4(), branch_id=uuid.uuid4(),
        beats=None, characters=None, themes=None, settings=None, issues=None,
    )
    specs = cat.tool_specs()
    names = {s["name"] for s in specs}

    assert len(specs) == 14
    assert "get_beat_entities" in names
    # the analytical wave is now wired in alongside the retrieval tools
    assert {"find_logic_error", "scan_branch", "classify_arc", "framework_anomalies"} <= names
    for s in specs:
        assert set(s) == {"name", "description", "input_schema"}
        assert s["input_schema"]["type"] == "object"
