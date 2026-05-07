"""
GraphRepo — T-003.

Architectural invariants enforced here:
  #2: All branch-scoped reads go through BranchScopedGraphRepo.for_branch(branch_id)
  #9: The WHERE branch_id = ANY(branch_tags) filter lives ONLY in this module

Two implementations ship in the same file:
  - PostgresGraphRepo  — real, async SQLAlchemy
  - InMemoryGraphRepo  — for tests + mock backend (T-004)
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.models import (
    AddBranchTagOp,
    AddEdgeOp,
    AddNodeOp,
    AppliedDelta,
    Edge,
    GraphDelta,
    Node,
    NodeStatus,
    NodeType,
    SetStatusOp,
    UpdatePropertyOp,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Abstract interfaces ───────────────────────────────────────────────────────

class BranchScopedGraphRepo(ABC):
    """Read/write interface scoped to a single branch. The only way to access nodes/edges."""

    @abstractmethod
    async def get_node(self, node_id: UUID) -> Node | None: ...

    @abstractmethod
    async def list_nodes(
        self,
        *,
        type: NodeType | None = None,
        status: NodeStatus | None = None,
    ) -> list[Node]: ...

    @abstractmethod
    async def get_edges_from(self, node_id: UUID) -> list[Edge]: ...

    @abstractmethod
    async def get_edges_to(self, node_id: UUID) -> list[Edge]: ...

    @abstractmethod
    async def list_edges(self) -> list[Edge]: ...

    @abstractmethod
    async def apply_delta(self, delta: GraphDelta) -> AppliedDelta:
        """Apply atomically. Returns the resulting touched entities."""

    @abstractmethod
    async def find_by_embedding(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[Node]: ...


class GraphRepo(ABC):
    @abstractmethod
    async def for_branch(self, branch_id: UUID) -> BranchScopedGraphRepo: ...


# ── InMemory implementation ───────────────────────────────────────────────────

class InMemoryBranchScopedGraphRepo(BranchScopedGraphRepo):
    """In-memory scoped repo. Filters nodes/edges by branch_id in branch_tags."""

    def __init__(
        self,
        nodes: dict[UUID, Node],
        edges: dict[UUID, Edge],
        branch_id: UUID,
    ) -> None:
        self._all_nodes = nodes
        self._all_edges = edges
        self._branch_id = branch_id

    def _node_in_branch(self, node: Node) -> bool:
        return self._branch_id in node.branch_tags

    def _edge_in_branch(self, edge: Edge) -> bool:
        return self._branch_id in edge.branch_tags

    async def get_node(self, node_id: UUID) -> Node | None:
        node = self._all_nodes.get(node_id)
        return deepcopy(node) if node and self._node_in_branch(node) else None

    async def list_nodes(
        self, *, type: NodeType | None = None, status: NodeStatus | None = None
    ) -> list[Node]:
        results = [
            deepcopy(n) for n in self._all_nodes.values() if self._node_in_branch(n)
        ]
        if type is not None:
            results = [n for n in results if n.type == type]
        if status is not None:
            results = [n for n in results if n.status == status]
        return results

    async def get_edges_from(self, node_id: UUID) -> list[Edge]:
        return [
            deepcopy(e)
            for e in self._all_edges.values()
            if e.source_id == node_id and self._edge_in_branch(e)
        ]

    async def get_edges_to(self, node_id: UUID) -> list[Edge]:
        return [
            deepcopy(e)
            for e in self._all_edges.values()
            if e.target_id == node_id and self._edge_in_branch(e)
        ]

    async def list_edges(self) -> list[Edge]:
        return [deepcopy(e) for e in self._all_edges.values() if self._edge_in_branch(e)]

    async def apply_delta(self, delta: GraphDelta) -> AppliedDelta:
        """Apply all ops atomically (all-or-nothing via snapshot rollback on error)."""
        # Snapshot for rollback
        nodes_snapshot = deepcopy(self._all_nodes)
        edges_snapshot = deepcopy(self._all_edges)

        affected_node_ids: list[UUID] = []
        affected_edge_ids: list[UUID] = []

        try:
            for op in delta.ops:
                if isinstance(op, AddNodeOp):
                    node = deepcopy(op.node)
                    node.created_at = datetime.utcnow()
                    node.updated_at = datetime.utcnow()
                    self._all_nodes[node.id] = node
                    affected_node_ids.append(node.id)

                elif isinstance(op, AddEdgeOp):
                    edge = deepcopy(op.edge)
                    self._all_edges[edge.id] = edge
                    affected_edge_ids.append(edge.id)

                elif isinstance(op, UpdatePropertyOp):
                    node = self._all_nodes.get(op.node_id)
                    if node is None:
                        raise ValueError(f"Node {op.node_id} not found for update_property")
                    node.properties[op.key] = op.value
                    node.updated_at = datetime.utcnow()
                    affected_node_ids.append(op.node_id)

                elif isinstance(op, SetStatusOp):
                    node = self._all_nodes.get(op.node_id)
                    if node is None:
                        raise ValueError(f"Node {op.node_id} not found for set_status")
                    node.status = op.status
                    node.updated_at = datetime.utcnow()
                    affected_node_ids.append(op.node_id)

                elif isinstance(op, AddBranchTagOp):
                    if op.entity_kind == "node":
                        entity = self._all_nodes.get(op.entity_id)
                        if entity is None:
                            raise ValueError(f"Node {op.entity_id} not found for add_branch_tag")
                        if op.branch_id not in entity.branch_tags:
                            entity.branch_tags.append(op.branch_id)
                        affected_node_ids.append(op.entity_id)
                    else:
                        entity = self._all_edges.get(op.entity_id)
                        if entity is None:
                            raise ValueError(f"Edge {op.entity_id} not found for add_branch_tag")
                        if op.branch_id not in entity.branch_tags:
                            entity.branch_tags.append(op.branch_id)
                        affected_edge_ids.append(op.entity_id)

        except Exception:
            # Rollback
            self._all_nodes.clear()
            self._all_nodes.update(nodes_snapshot)
            self._all_edges.clear()
            self._all_edges.update(edges_snapshot)
            raise

        return AppliedDelta(
            delta=delta,
            affected_node_ids=list(set(affected_node_ids)),
            affected_edge_ids=list(set(affected_edge_ids)),
        )

    async def find_by_embedding(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[Node]:
        """In-memory: return all nodes (no vector search). Real impl uses pgvector."""
        nodes = await self.list_nodes()
        return nodes[:limit]


class InMemoryGraphRepo(GraphRepo):
    """Module-level singleton used by the mock backend and all unit tests."""

    def __init__(self) -> None:
        self._nodes: dict[UUID, Node] = {}
        self._edges: dict[UUID, Edge] = {}

    async def for_branch(self, branch_id: UUID) -> InMemoryBranchScopedGraphRepo:
        return InMemoryBranchScopedGraphRepo(self._nodes, self._edges, branch_id)

    def reset(self) -> None:
        """Clear all state — useful between tests."""
        self._nodes.clear()
        self._edges.clear()


# ── Postgres implementation (stub — full impl in Week 2) ─────────────────────

class PostgresBranchScopedGraphRepo(BranchScopedGraphRepo):
    """
    Real branch-scoped repo. All queries use:
      WHERE :branch_id = ANY(branch_tags)
    That filter lives ONLY here — invariant #9.
    """

    def __init__(self, session: "AsyncSession", branch_id: UUID) -> None:
        self._session = session
        self._branch_id = branch_id

    async def get_node(self, node_id: UUID) -> Node | None:
        raise NotImplementedError("PostgresGraphRepo not yet implemented — use InMemoryGraphRepo")

    async def list_nodes(
        self, *, type: NodeType | None = None, status: NodeStatus | None = None
    ) -> list[Node]:
        raise NotImplementedError

    async def get_edges_from(self, node_id: UUID) -> list[Edge]:
        raise NotImplementedError

    async def get_edges_to(self, node_id: UUID) -> list[Edge]:
        raise NotImplementedError

    async def list_edges(self) -> list[Edge]:
        raise NotImplementedError

    async def apply_delta(self, delta: GraphDelta) -> AppliedDelta:
        raise NotImplementedError

    async def find_by_embedding(
        self, query_embedding: list[float], limit: int = 10
    ) -> list[Node]:
        raise NotImplementedError


class PostgresGraphRepo(GraphRepo):
    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    async def for_branch(self, branch_id: UUID) -> PostgresBranchScopedGraphRepo:
        return PostgresBranchScopedGraphRepo(self._session, branch_id)
