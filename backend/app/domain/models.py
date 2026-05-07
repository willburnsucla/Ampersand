"""
Core Pydantic v2 domain models.
These match the JSON schemas in /shared/schemas/ exactly.
Do NOT hand-edit /domain/generated/ — that's codegen output.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

NodeType = Literal["character", "beat", "theme", "world_element", "thread"]
NodeStatus = Literal["proposed", "committed", "rejected"]
EdgeRelation = Literal["participates_in", "introduced_by", "contradicts", "supports", "depends_on"]
BranchState = Literal["active", "dormant", "committed", "graveyard"]


# ── Per-subtype property schemas ──────────────────────────────────────────────

class CharacterProperties(BaseModel):
    name: str
    description: str
    traits: list[str] = Field(default_factory=list)


class BeatProperties(BaseModel):
    title: str
    description: str
    sequence_index: float
    participant_ids: list[UUID] = Field(default_factory=list)


class ThemeProperties(BaseModel):
    name: str
    description: str


class WorldElementProperties(BaseModel):
    name: str
    description: str
    rules: list[str] = Field(default_factory=list)


class ThreadProperties(BaseModel):
    name: str
    setup_beat_id: UUID
    payoff_beat_id: UUID | None = None


# ── Node + Edge ───────────────────────────────────────────────────────────────

class Node(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    story_id: UUID
    type: NodeType
    status: NodeStatus = "proposed"
    branch_tags: list[UUID] = Field(default_factory=list)
    provenance_turn_id: UUID  # non-null — enforced here + DB
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Edge(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    source_id: UUID
    target_id: UUID
    relation: EdgeRelation
    branch_tags: list[UUID] = Field(default_factory=list)
    provenance_turn_id: UUID  # non-null


# ── GraphDelta ops ────────────────────────────────────────────────────────────

class AddNodeOp(BaseModel):
    kind: Literal["add_node"] = "add_node"
    node: Node


class AddEdgeOp(BaseModel):
    kind: Literal["add_edge"] = "add_edge"
    edge: Edge


class UpdatePropertyOp(BaseModel):
    kind: Literal["update_property"] = "update_property"
    node_id: UUID
    key: str
    value: Any


class SetStatusOp(BaseModel):
    kind: Literal["set_status"] = "set_status"
    node_id: UUID
    status: NodeStatus


class AddBranchTagOp(BaseModel):
    kind: Literal["add_branch_tag"] = "add_branch_tag"
    entity_kind: Literal["node", "edge"]
    entity_id: UUID
    branch_id: UUID


DeltaOp = Union[AddNodeOp, AddEdgeOp, UpdatePropertyOp, SetStatusOp, AddBranchTagOp]


class GraphDelta(BaseModel):
    """Command produced by Extractor, applied by DeltaApplier."""
    turn_id: UUID
    ops: list[DeltaOp] = Field(default_factory=list)


# ── Applied delta (result from DeltaApplier) ─────────────────────────────────

class AppliedDelta(BaseModel):
    delta: GraphDelta
    affected_node_ids: list[UUID] = Field(default_factory=list)
    affected_edge_ids: list[UUID] = Field(default_factory=list)


# ── SSE event ─────────────────────────────────────────────────────────────────

class GraphDeltaEvent(BaseModel):
    schema_version: Literal[1] = 1
    story_id: UUID
    branch_id: UUID
    turn_id: UUID
    sequence_number: int = Field(ge=1)  # monotonic per (story_id, branch_id)
    applied_ops: list[DeltaOp] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Graph snapshot ────────────────────────────────────────────────────────────

class GraphSnapshot(BaseModel):
    story_id: UUID
    branch_id: UUID
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    last_applied_sequence: int = Field(ge=0, default=0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Transport DTOs ────────────────────────────────────────────────────────────

class Story(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    owner_id: str  # clerk_user_id
    title: str
    active_branch_id: UUID | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreateStoryInput(BaseModel):
    title: str


class Branch(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    story_id: UUID
    parent_branch_id: UUID | None = None
    state: BranchState = "active"
    created_from_beat_id: UUID | None = None
    name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreateBranchInput(BaseModel):
    story_id: UUID
    parent_branch_id: UUID | None = None
    created_from_beat_id: UUID | None = None
    name: str | None = None


class BranchTransitionInput(BaseModel):
    event: Literal["switch_to_active", "switch_to_dormant", "commit", "abandon", "revive"]


class TurnRequest(BaseModel):
    story_id: UUID
    branch_id: UUID
    content: str = Field(min_length=1, max_length=32000)


class TurnResult(BaseModel):
    turn_id: UUID
    reply: str
    applied_delta: AppliedDelta


class ConversationTurn(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    story_id: UUID
    branch_id: UUID
    role: Literal["writer", "assistant"]
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QueryInput(BaseModel):
    story_id: UUID
    branch_id: UUID
    question: str = Field(min_length=1)


class Citation(BaseModel):
    kind: Literal["turn", "node"]
    id: UUID
    excerpt: str


class QueryAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: Literal["grounded", "not_in_graph"]


class Gap(BaseModel):
    id: str
    category: Literal["missing_arc", "undefined_relationship", "orphan_thread", "thin_character", "open_question"]
    title: str
    description: str
    related_node_ids: list[UUID] = Field(default_factory=list)
    suggested_question: str


class ExportResult(BaseModel):
    markdown: str
    cited_turn_ids: list[UUID] = Field(default_factory=list)
    branch_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
