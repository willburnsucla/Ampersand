"""v2 domain contract — Pydantic models for the wire/UI surface. No ORM or SQL."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

EntityStatus = Literal["proposed", "committed", "rejected"]
BranchState  = Literal["active", "dormant", "committed", "graveyard"]
TurnRole     = Literal["writer", "assistant"]

IssueType    = Literal[
    "contradiction",
    "timeline_gap",
    "character_inconsistency",
    "world_rule_violation",
    "pacing_anomaly",
    "framework_misuse",
]
IssueStatus  = Literal["open", "acknowledged", "resolved"]

# these are just the labels for the narrative analysis — the actual functions
# live in narrative.py.
#
# TurningPoint is capped at 5 because thats what papalampidi has, but really
# these are kinds not ordinals (the order's already in sequence_index_in_branch).
# if we ever want longer stories with subplots or stuff like double-man-in-hole
# (which needs two dips), the move is probably to switch to semantic kinds —
# opportunity, change_of_plans, major_setback, etc — and let multiple beats
# share one. only catch is classify_arc would need a tiebreaker to pick THE
# major setback when there's more than one.
VonnegutArc  = Literal[
    "rags_to_riches", "riches_to_rags",
    "man_in_hole",    "double_man_in_hole",
    "icarus",         "cinderella", "oedipus",
]
TurningPoint = Literal["tp1", "tp2", "tp3", "tp4", "tp5"]


# ── Top-level container ───────────────────────────────────────────────────────

class Project(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    owner_id: str
    title: str
    primary_branch_id: UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Branches (git-style: one primary + tree-recursive alternates) ─────────────

class Branch(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    project_id: UUID
    parent_branch_id: UUID | None = None
    created_from_beat_id: UUID | None = None
    name: str | None = None
    state: BranchState = "active"
    declared_arc: VonnegutArc | None = None   # writer-set only; inferred arcs are computed on demand
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Beats (the only story-graph node type) ────────────────────────────────────

class Beat(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    branch_id: UUID
    sequence_index_in_branch: int
    logline: str
    content: dict[str, Any] = Field(default_factory=dict)
    turning_point: TurningPoint | None = None
    valence: float | None = Field(default=None, ge=0, le=1)
    arousal: float | None = Field(default=None, ge=0, le=1)
    status: EntityStatus = "proposed"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── First-class project entities (Model 3: base + branch overlay) ─────────────

class Character(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    project_id: UUID
    name: str
    base_properties: dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = "committed"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Theme(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    project_id: UUID
    name: str
    base_properties: dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = "committed"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Setting(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    project_id: UUID
    name: str
    base_properties: dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = "committed"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Views: frozen read-projections (base ⊕ branch overlay merged) ─────────────

class _ViewBase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    properties: dict[str, Any]
    resolved_in_branch: UUID


class CharacterView(_ViewBase): pass
class ThemeView(_ViewBase): pass
class SettingView(_ViewBase): pass


# ── Issues (bot-detected, persisted, lifecycle-tracked) ───────────────────────

class Issue(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    branch_id: UUID
    type: IssueType
    description: str
    related_beat_ids: list[UUID] = Field(default_factory=list)
    related_entity_ids: list[UUID] = Field(default_factory=list)
    status: IssueStatus = "open"
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None


# ── Conversation log ──────────────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    branch_id: UUID
    role: TurnRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
