"""
Extractor — T-006 interface + MockExtractor (T-004 unblocked here).

Architectural invariant #5: the Anthropic SDK is ONLY imported inside this file.
No other module may call the LLM directly.

ClaudeExtractor: real implementation using Anthropic tool use (structured output).
MockExtractor:   deterministic, no external calls — used by T-004 and all unit tests.

Both live in the same file (invariant #7).
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.models import (
    AddNodeOp,
    AppliedDelta,
    CharacterProperties,
    GraphDelta,
    Node,
)

if TYPE_CHECKING:
    pass


# ── Interface ─────────────────────────────────────────────────────────────────

class LlmContext:
    """Built by ContextBuilder (T-007); fed to Extractor."""

    def __init__(
        self,
        *,
        branch_summary: str = "",
        recent_turns: list = None,
        relevant_nodes: list = None,
        user_message: str,
    ) -> None:
        self.branch_summary = branch_summary
        self.recent_turns = recent_turns or []
        self.relevant_nodes = relevant_nodes or []
        self.user_message = user_message


class ExtractionResult:
    def __init__(self, *, reply: str, delta: GraphDelta) -> None:
        self.reply = reply
        self.delta = delta


class Extractor(ABC):
    @abstractmethod
    async def extract(self, context: LlmContext, *, turn_id: UUID) -> ExtractionResult: ...


# ── MockExtractor ─────────────────────────────────────────────────────────────

_KEYWORD_MAP = {
    "detective": ("character", {"name": "Maya", "description": "A detective", "traits": ["sharp", "observant"]}),
    "wizard":    ("character", {"name": "Alaric", "description": "A wizard", "traits": ["wise", "mysterious"]}),
    "forest":    ("world_element", {"name": "The Dark Forest", "description": "A dangerous forest", "rules": ["no magic inside"]}),
    "chapter":   ("beat", {"title": "Opening", "description": "The story begins", "sequence_index": 1.0, "participant_ids": []}),
    "theme":     ("theme", {"name": "Justice", "description": "The pursuit of truth"}),
}

_DEFAULT_NODE = ("character", {
    "name": "Unnamed Character",
    "description": "A character introduced in this turn",
    "traits": [],
})


class MockExtractor(Extractor):
    """
    Deterministic extractor for dev and tests.
    Scans user_message for keywords and emits a matching node.
    Always returns the same node for the same keyword (idempotent).
    """

    async def extract(self, context: LlmContext, *, turn_id: UUID) -> ExtractionResult:
        msg_lower = context.user_message.lower()

        node_type, properties = _DEFAULT_NODE
        for keyword, (ntype, props) in _KEYWORD_MAP.items():
            if keyword in msg_lower:
                node_type, properties = ntype, props
                break

        node_id = uuid.uuid5(uuid.NAMESPACE_OID, f"{turn_id}:{node_type}:{properties.get('name','')}")

        node = Node(
            id=node_id,
            story_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),  # placeholder; caller patches
            type=node_type,  # type: ignore[arg-type]
            status="committed",
            branch_tags=[],  # caller patches
            provenance_turn_id=turn_id,
            properties=properties,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        delta = GraphDelta(
            turn_id=turn_id,
            ops=[AddNodeOp(node=node)],
        )

        reply = (
            f"I've noted that in your story. "
            f"I've added a {node_type} node: '{properties.get('name', 'Unnamed')}'."
        )

        return ExtractionResult(reply=reply, delta=delta)


# ── ClaudeExtractor (stub — full impl in T-006 Week 2) ───────────────────────

class ClaudeExtractor(Extractor):
    """
    Real implementation using Anthropic SDK tool use for structured output.
    Default model: claude-haiku-4-5. Escalates to claude-sonnet-4-6 on parse failure.

    Architectural invariant #5: `import anthropic` ONLY appears in this file.
    """

    def __init__(self, *, default_model: str = "claude-haiku-4-5") -> None:
        self._default_model = default_model

    async def extract(self, context: LlmContext, *, turn_id: UUID) -> ExtractionResult:
        raise NotImplementedError(
            "ClaudeExtractor not yet implemented — use MockExtractor for now (T-006 Week 2)"
        )
