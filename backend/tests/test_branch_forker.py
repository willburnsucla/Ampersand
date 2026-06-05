"""Integration tests for BranchForker against a real Postgres."""
import uuid

import pytest

from app.domain.orm_v2 import BranchOrm, ProjectOrm
from app.repos.beat_repo import SqlBeatRepo
from app.repos.branch_repo import SqlBranchRepo
from app.services.branch_forker import BranchForker


async def _seed(db_session):
    project = ProjectOrm(owner_id="user-1", title="proj")
    db_session.add(project)
    await db_session.flush()
    parent = BranchOrm(project_id=project.id, name="main")
    db_session.add(parent)
    await db_session.flush()
    return project, parent


def _forker(db_session) -> BranchForker:
    return BranchForker(beats=SqlBeatRepo(db_session), branches=SqlBranchRepo(db_session))


async def _add_beats(db_session, branch_id, loglines):
    beats = SqlBeatRepo(db_session)
    return [
        await beats.create(branch_id=branch_id, sequence_index_in_branch=i, logline=logline)
        for i, logline in enumerate(loglines)
    ]


# forking at a beat carries the story up to and including that beat into the new branch
async def test_fork_inherits_history_up_to_the_beat(db_session):
    project, parent = await _seed(db_session)
    beats = await _add_beats(db_session, parent.id, ["one", "two", "three", "four"])

    fork = await _forker(db_session).fork(
        project_id=project.id, parent_branch_id=parent.id,
        from_beat_id=beats[1].id, name="what-if",
    )

    assert fork.parent_branch_id == parent.id
    assert fork.created_from_beat_id == beats[1].id
    carried = await SqlBeatRepo(db_session).list(branch_id=fork.id)
    assert [b.logline for b in carried] == ["one", "two"]  # 2 and 3 left behind
    assert [b.sequence_index_in_branch for b in carried] == [0, 1]


# the parent branch is untouched by the fork
async def test_fork_leaves_the_parent_intact(db_session):
    project, parent = await _seed(db_session)
    beats = await _add_beats(db_session, parent.id, ["one", "two", "three"])
    await _forker(db_session).fork(
        project_id=project.id, parent_branch_id=parent.id, from_beat_id=beats[0].id,
    )
    parent_beats = await SqlBeatRepo(db_session).list(branch_id=parent.id)
    assert [b.logline for b in parent_beats] == ["one", "two", "three"]


# a beat that is not in the parent branch is rejected
async def test_fork_rejects_a_foreign_beat(db_session):
    project, parent = await _seed(db_session)
    with pytest.raises(ValueError, match="not in branch"):
        await _forker(db_session).fork(
            project_id=project.id, parent_branch_id=parent.id, from_beat_id=uuid.uuid4(),
        )


# the per-beat fork cap of three is enforced through the service
async def test_fork_respects_the_three_cap(db_session):
    project, parent = await _seed(db_session)
    beats = await _add_beats(db_session, parent.id, ["one"])
    for i in range(3):
        await _forker(db_session).fork(
            project_id=project.id, parent_branch_id=parent.id,
            from_beat_id=beats[0].id, name=f"alt-{i}",
        )
    with pytest.raises(ValueError, match="cap is 3"):
        await _forker(db_session).fork(
            project_id=project.id, parent_branch_id=parent.id,
            from_beat_id=beats[0].id, name="alt-4",
        )
