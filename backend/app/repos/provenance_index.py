"""
ProvenanceIndex — T-003.
Maps turn_id → affected nodes/edges and node_id → introducing turn.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from uuid import UUID


class ProvenanceIndex(ABC):
    @abstractmethod
    async def get_introducing_turn(self, node_id: UUID) -> UUID | None: ...

    @abstractmethod
    async def get_affected_nodes(self, turn_id: UUID) -> list[UUID]: ...

    @abstractmethod
    async def get_affected_edges(self, turn_id: UUID) -> list[UUID]: ...

    @abstractmethod
    async def record(
        self,
        turn_id: UUID,
        node_ids: list[UUID],
        edge_ids: list[UUID],
    ) -> None: ...


class InMemoryProvenanceIndex(ProvenanceIndex):
    def __init__(self) -> None:
        self._node_to_turn: dict[UUID, UUID] = {}
        self._turn_to_nodes: dict[UUID, list[UUID]] = defaultdict(list)
        self._turn_to_edges: dict[UUID, list[UUID]] = defaultdict(list)

    async def get_introducing_turn(self, node_id: UUID) -> UUID | None:
        return self._node_to_turn.get(node_id)

    async def get_affected_nodes(self, turn_id: UUID) -> list[UUID]:
        return list(self._turn_to_nodes.get(turn_id, []))

    async def get_affected_edges(self, turn_id: UUID) -> list[UUID]:
        return list(self._turn_to_edges.get(turn_id, []))

    async def record(
        self,
        turn_id: UUID,
        node_ids: list[UUID],
        edge_ids: list[UUID],
    ) -> None:
        for nid in node_ids:
            self._node_to_turn.setdefault(nid, turn_id)
            if nid not in self._turn_to_nodes[turn_id]:
                self._turn_to_nodes[turn_id].append(nid)
        for eid in edge_ids:
            if eid not in self._turn_to_edges[turn_id]:
                self._turn_to_edges[turn_id].append(eid)

    def reset(self) -> None:
        self._node_to_turn.clear()
        self._turn_to_nodes.clear()
        self._turn_to_edges.clear()


class PostgresProvenanceIndex(ProvenanceIndex):
    async def get_introducing_turn(self, node_id: UUID) -> UUID | None:
        raise NotImplementedError

    async def get_affected_nodes(self, turn_id: UUID) -> list[UUID]:
        raise NotImplementedError

    async def get_affected_edges(self, turn_id: UUID) -> list[UUID]:
        raise NotImplementedError

    async def record(
        self,
        turn_id: UUID,
        node_ids: list[UUID],
        edge_ids: list[UUID],
    ) -> None:
        raise NotImplementedError
