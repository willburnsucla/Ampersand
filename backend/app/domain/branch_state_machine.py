"""
BranchStateMachine — T-005.

Pure logic module, no I/O, no DB. Validates which branch transitions are legal.
Consumers (BranchRepo, route handlers) own persistence; this module only validates.

Branch states (spec-locked):
  active    — writer is actively working on this branch
  dormant   — parked but can be revived
  committed — terminal; cannot transition further
  graveyard — abandoned; can be revived to active

Allowed transitions:
  (creation) → active                 via CREATE
  active  →  dormant                  via SWITCH_TO_DORMANT
  dormant →  active                   via SWITCH_TO_ACTIVE
  active  →  committed                via COMMIT  (terminal)
  active  →  graveyard                via ABANDON
  dormant →  graveyard                via ABANDON
  graveyard → active                  via REVIVE
"""
from __future__ import annotations

from enum import Enum


class BranchEvent(str, Enum):
    CREATE = "create"
    SWITCH_TO_ACTIVE = "switch_to_active"
    SWITCH_TO_DORMANT = "switch_to_dormant"
    COMMIT = "commit"
    ABANDON = "abandon"
    REVIVE = "revive"


class InvalidTransitionError(Exception):
    """Raised when a branch transition is not allowed by the state machine."""


# Allowed transitions: from_state → {allowed events}
_ALLOWED: dict[str, set[BranchEvent]] = {
    "active":    {BranchEvent.SWITCH_TO_DORMANT, BranchEvent.COMMIT, BranchEvent.ABANDON},
    "dormant":   {BranchEvent.SWITCH_TO_ACTIVE, BranchEvent.ABANDON},
    "graveyard": {BranchEvent.REVIVE},
    "committed": set(),  # terminal state — no outgoing transitions
}

# Result of each valid (from_state, event) pair
_NEXT_STATE: dict[tuple[str, BranchEvent], str] = {
    ("active",    BranchEvent.SWITCH_TO_DORMANT): "dormant",
    ("active",    BranchEvent.COMMIT):            "committed",
    ("active",    BranchEvent.ABANDON):           "graveyard",
    ("dormant",   BranchEvent.SWITCH_TO_ACTIVE):  "active",
    ("dormant",   BranchEvent.ABANDON):           "graveyard",
    ("graveyard", BranchEvent.REVIVE):            "active",
}


class BranchStateMachine:
    """Static helper — no instance state."""

    @staticmethod
    def can_transition(current_state: str, event: BranchEvent) -> bool:
        """Return True if the transition is allowed; False otherwise."""
        return event in _ALLOWED.get(current_state, set())

    @staticmethod
    def next_state(current_state: str, event: BranchEvent) -> str:
        """
        Return the resulting state after applying event.
        Raises InvalidTransitionError if the transition is not allowed.
        """
        key = (current_state, event)
        if key not in _NEXT_STATE:
            allowed = _ALLOWED.get(current_state, set())
            if not allowed:
                raise InvalidTransitionError(
                    f"Branch in state '{current_state}' is terminal — no transitions allowed."
                )
            raise InvalidTransitionError(
                f"Cannot transition branch from '{current_state}' via '{event.value}'. "
                f"Allowed events: {[e.value for e in allowed]}"
            )
        return _NEXT_STATE[key]
