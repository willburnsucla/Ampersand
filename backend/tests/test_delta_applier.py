"""Integration tests for DeltaApplier against a real Postgres."""
from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.beat_repo import SqlBeatRepo
from app.repos.character_repo import SqlCharacterRepo
from app.repos.setting_repo import SqlSettingRepo
from app.repos.theme_repo import SqlThemeRepo
from app.services.delta_applier import DeltaApplier
from app.services.extractor_v2 import ProposedBeat


async def _seed(db_session):
    project = ProjectOrm(owner_id="user-1", title="proj")
    db_session.add(project)
    await db_session.flush()
    branch = BranchOrm(project_id=project.id, name="main")
    db_session.add(branch)
    await db_session.flush()
    return project, branch


def _applier(db_session) -> DeltaApplier:
    return DeltaApplier(
        beats=SqlBeatRepo(db_session),
        characters=SqlCharacterRepo(db_session),
        themes=SqlThemeRepo(db_session),
        settings=SqlSettingRepo(db_session),
    )


# beats land as proposed and the sequence index climbs from zero
async def test_apply_assigns_next_sequence_index(db_session):
    project, branch = await _seed(db_session)
    applier = _applier(db_session)
    b0 = await applier.apply_proposed_beat(
        ProposedBeat(logline="one"), project_id=project.id, branch_id=branch.id
    )
    b1 = await applier.apply_proposed_beat(
        ProposedBeat(logline="two"), project_id=project.id, branch_id=branch.id
    )
    assert b0.sequence_index_in_branch == 0
    assert b1.sequence_index_in_branch == 1
    assert b0.status == "proposed"


# named entities are created and linked to the beat
async def test_apply_creates_and_links_entities(db_session):
    project, branch = await _seed(db_session)
    beat = await _applier(db_session).apply_proposed_beat(
        ProposedBeat(logline="Maya enters", character_names=["Maya"], theme_names=["Justice"]),
        project_id=project.id, branch_id=branch.id,
    )
    chars = await SqlCharacterRepo(db_session).list_for_beat(beat.id, project_id=project.id)
    themes = await SqlThemeRepo(db_session).list_for_beat(beat.id, project_id=project.id)
    assert {c.name for c in chars} == {"Maya"}
    assert {t.name for t in themes} == {"Justice"}


# an entity that already exists is reused by name, case-insensitively, not duplicated
async def test_apply_reuses_existing_entity_by_name(db_session):
    project, branch = await _seed(db_session)
    chars = SqlCharacterRepo(db_session)
    sarah = await chars.create(project_id=project.id, name="Sarah")

    beat = await _applier(db_session).apply_proposed_beat(
        ProposedBeat(logline="Sarah again", character_names=["sarah"]),
        project_id=project.id, branch_id=branch.id,
    )

    linked = await chars.list_for_beat(beat.id, project_id=project.id)
    assert [c.id for c in linked] == [sarah.id]
    assert len(await chars.list(project_id=project.id)) == 1


# confirm and reject move the beat's lifecycle status
async def test_confirm_and_reject_move_status(db_session):
    project, branch = await _seed(db_session)
    applier = _applier(db_session)
    beat = await applier.apply_proposed_beat(
        ProposedBeat(logline="x"), project_id=project.id, branch_id=branch.id
    )
    assert (await applier.confirm(beat.id, branch_id=branch.id)).status == "committed"
    assert (await applier.reject(beat.id, branch_id=branch.id)).status == "rejected"


# re-applying a beat with the same logline reuses it instead of writing a duplicate
async def test_apply_dedupes_a_repeated_logline(db_session):
    project, branch = await _seed(db_session)
    applier = _applier(db_session)
    first = await applier.apply_proposed_beat(
        ProposedBeat(logline="Sarah opens the door"), project_id=project.id, branch_id=branch.id
    )
    again = await applier.apply_proposed_beat(
        ProposedBeat(logline="Sarah opens the door"), project_id=project.id, branch_id=branch.id
    )
    assert again.id == first.id
    assert len(await SqlBeatRepo(db_session).list(branch_id=branch.id)) == 1


# dedup ignores case and surrounding whitespace
async def test_apply_dedup_is_case_and_whitespace_insensitive(db_session):
    project, branch = await _seed(db_session)
    applier = _applier(db_session)
    first = await applier.apply_proposed_beat(
        ProposedBeat(logline="The Ship Sails at Dawn"), project_id=project.id, branch_id=branch.id
    )
    again = await applier.apply_proposed_beat(
        ProposedBeat(logline="  the ship sails at dawn  "),
        project_id=project.id, branch_id=branch.id,
    )
    assert again.id == first.id
    assert len(await SqlBeatRepo(db_session).list(branch_id=branch.id)) == 1


# distinct loglines still create distinct, sequentially indexed beats
async def test_apply_keeps_distinct_loglines_separate(db_session):
    project, branch = await _seed(db_session)
    applier = _applier(db_session)
    a = await applier.apply_proposed_beat(
        ProposedBeat(logline="first beat"), project_id=project.id, branch_id=branch.id
    )
    b = await applier.apply_proposed_beat(
        ProposedBeat(logline="second beat"), project_id=project.id, branch_id=branch.id
    )
    assert a.id != b.id
    assert (a.sequence_index_in_branch, b.sequence_index_in_branch) == (0, 1)


# a duplicate reuses the beat without linking its entities a second time
async def test_apply_dedup_does_not_relink_entities(db_session):
    project, branch = await _seed(db_session)
    applier = _applier(db_session)
    first = await applier.apply_proposed_beat(
        ProposedBeat(logline="Maya enters", character_names=["Maya"]),
        project_id=project.id, branch_id=branch.id,
    )
    again = await applier.apply_proposed_beat(
        ProposedBeat(logline="Maya enters", character_names=["Maya"]),
        project_id=project.id, branch_id=branch.id,
    )
    assert again.id == first.id
    chars = await SqlCharacterRepo(db_session).list_for_beat(first.id, project_id=project.id)
    assert [c.name for c in chars] == ["Maya"]
    assert len(await SqlCharacterRepo(db_session).list(project_id=project.id)) == 1


# a single beat can carry characters, themes, and settings together, all created and linked
async def test_apply_links_all_three_entity_types(db_session):
    project, branch = await _seed(db_session)
    beat = await _applier(db_session).apply_proposed_beat(
        ProposedBeat(
            logline="Maya hunts for justice at the old harbor",
            character_names=["Maya"], theme_names=["Justice"], setting_names=["Old Harbor"],
        ),
        project_id=project.id, branch_id=branch.id,
    )
    chars = await SqlCharacterRepo(db_session).list_for_beat(beat.id, project_id=project.id)
    themes = await SqlThemeRepo(db_session).list_for_beat(beat.id, project_id=project.id)
    settings = await SqlSettingRepo(db_session).list_for_beat(beat.id, project_id=project.id)
    assert {c.name for c in chars} == {"Maya"}
    assert {t.name for t in themes} == {"Justice"}
    assert {s.name for s in settings} == {"Old Harbor"}
