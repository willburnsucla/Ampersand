"""
Unit tests for BranchStateMachine (T-005).
100% branch coverage required per Definition of Done.
"""
import pytest

from app.domain.branch_state_machine import BranchEvent, BranchStateMachine, InvalidTransitionError


# ── Allowed transitions ───────────────────────────────────────────────────────

@pytest.mark.parametrize("from_state, event, expected", [
    ("active",    BranchEvent.SWITCH_TO_DORMANT, "dormant"),
    ("active",    BranchEvent.COMMIT,            "committed"),
    ("active",    BranchEvent.ABANDON,           "graveyard"),
    ("dormant",   BranchEvent.SWITCH_TO_ACTIVE,  "active"),
    ("dormant",   BranchEvent.ABANDON,           "graveyard"),
    ("graveyard", BranchEvent.REVIVE,            "active"),
])
def test_allowed_transitions(from_state, event, expected):
    assert BranchStateMachine.next_state(from_state, event) == expected


# ── can_transition ────────────────────────────────────────────────────────────

def test_can_transition_true():
    assert BranchStateMachine.can_transition("active", BranchEvent.COMMIT) is True


def test_can_transition_false():
    assert BranchStateMachine.can_transition("committed", BranchEvent.REVIVE) is False


# ── Disallowed transitions ────────────────────────────────────────────────────

@pytest.mark.parametrize("from_state, event", [
    ("committed", BranchEvent.COMMIT),
    ("committed", BranchEvent.SWITCH_TO_ACTIVE),
    ("committed", BranchEvent.SWITCH_TO_DORMANT),
    ("committed", BranchEvent.ABANDON),
    ("committed", BranchEvent.REVIVE),
    ("active",    BranchEvent.REVIVE),
    ("dormant",   BranchEvent.COMMIT),
    ("dormant",   BranchEvent.REVIVE),
    ("graveyard", BranchEvent.COMMIT),
    ("graveyard", BranchEvent.SWITCH_TO_DORMANT),
])
def test_disallowed_transitions_raise(from_state, event):
    with pytest.raises(InvalidTransitionError):
        BranchStateMachine.next_state(from_state, event)


def test_committed_is_terminal():
    """COMMIT from Committed must raise, it's a terminal state."""
    with pytest.raises(InvalidTransitionError, match="terminal"):
        BranchStateMachine.next_state("committed", BranchEvent.COMMIT)


def test_graveyard_revive_returns_active():
    assert BranchStateMachine.next_state("graveyard", BranchEvent.REVIVE) == "active"


def test_active_can_toggle_dormant_roundtrip():
    state = "active"
    state = BranchStateMachine.next_state(state, BranchEvent.SWITCH_TO_DORMANT)
    assert state == "dormant"
    state = BranchStateMachine.next_state(state, BranchEvent.SWITCH_TO_ACTIVE)
    assert state == "active"
