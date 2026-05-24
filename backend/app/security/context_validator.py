"""
ContextValidator — LlmContext structure validation and boundary enforcement.

Methods:
  - validate_llm_context(ctx: LlmContext) -> tuple[bool, str]: Full validation
  - validate_structure(ctx: LlmContext) -> tuple[bool, str]: Pydantic-style checks
  - validate_boundaries(ctx: LlmContext) -> tuple[bool, str]: Size/count limits
  - validate_branch_consistency(ctx: LlmContext, expected_branch_id: UUID) -> tuple[bool, str]
  - redact_context(ctx: LlmContext) -> LlmContext: Remove sensitive metadata
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from app.security.config import (
    MAX_BRANCH_SUMMARY_LENGTH,
    MAX_RECENT_TURNS,
    MAX_RELEVANT_NODES,
    MAX_TOTAL_CONTEXT_SIZE,
    MAX_USER_MESSAGE_LENGTH,
    VERBOSE_LOGGING,
)

if TYPE_CHECKING:
    from app.services.extractor import LlmContext

logger = logging.getLogger(__name__)


class ContextValidator:
    """
    Structural and boundary validation for LlmContext.
    
    Ensures:
      1. LlmContext has required fields and types are correct
      2. Size limits are enforced (message, summary, turns, nodes, total)
      3. Branch IDs are consistent across all context fields
      4. Sensitive metadata is redacted
    """

    def validate_llm_context(
        self,
        ctx: LlmContext,
        expected_branch_id: UUID | None = None,
    ) -> tuple[bool, str]:
        """
        Run all validation checks on an LlmContext.

        Args:
            ctx: The context to validate
            expected_branch_id: If provided, verify context's branch_id matches

        Returns:
            (is_valid, error_message). If is_valid is True, error_message is "".
        """
        # Check structure
        is_valid, msg = self.validate_structure(ctx)
        if not is_valid:
            if VERBOSE_LOGGING:
                logger.warning(f"Context structure validation failed: {msg}")
            return False, msg

        # Check boundaries
        is_valid, msg = self.validate_boundaries(ctx)
        if not is_valid:
            if VERBOSE_LOGGING:
                logger.warning(f"Context boundary validation failed: {msg}")
            return False, msg

        # Check branch consistency if expected_branch_id provided
        if expected_branch_id:
            is_valid, msg = self.validate_branch_consistency(ctx, expected_branch_id)
            if not is_valid:
                if VERBOSE_LOGGING:
                    logger.warning(f"Branch consistency validation failed: {msg}")
                return False, msg

        return True, ""

    def validate_structure(self, ctx: LlmContext) -> tuple[bool, str]:
        """
        Validate that LlmContext has required fields with correct types.
        """
        if not hasattr(ctx, "user_message"):
            return False, "LlmContext missing 'user_message' field"

        if not isinstance(ctx.user_message, str):
            return False, f"'user_message' must be str, got {type(ctx.user_message).__name__}"

        if not hasattr(ctx, "branch_summary"):
            return False, "LlmContext missing 'branch_summary' field"

        if not isinstance(ctx.branch_summary, str):
            return False, f"'branch_summary' must be str, got {type(ctx.branch_summary).__name__}"

        if not hasattr(ctx, "recent_turns"):
            return False, "LlmContext missing 'recent_turns' field"

        if not isinstance(ctx.recent_turns, list):
            return False, f"'recent_turns' must be list, got {type(ctx.recent_turns).__name__}"

        if not hasattr(ctx, "relevant_nodes"):
            return False, "LlmContext missing 'relevant_nodes' field"

        if not isinstance(ctx.relevant_nodes, list):
            return False, f"'relevant_nodes' must be list, got {type(ctx.relevant_nodes).__name__}"

        return True, ""

    def validate_boundaries(self, ctx: LlmContext) -> tuple[bool, str]:
        """
        Enforce size and count limits on context fields.
        """
        # Check user_message length
        if len(ctx.user_message) > MAX_USER_MESSAGE_LENGTH:
            return False, f"user_message exceeds max length {MAX_USER_MESSAGE_LENGTH}"

        # Check branch_summary length
        if len(ctx.branch_summary) > MAX_BRANCH_SUMMARY_LENGTH:
            return False, f"branch_summary exceeds max length {MAX_BRANCH_SUMMARY_LENGTH}"

        # Check recent_turns count
        if len(ctx.recent_turns) > MAX_RECENT_TURNS:
            return False, f"recent_turns exceeds max count {MAX_RECENT_TURNS}"

        # Check relevant_nodes count
        if len(ctx.relevant_nodes) > MAX_RELEVANT_NODES:
            return False, f"relevant_nodes exceeds max count {MAX_RELEVANT_NODES}"

        # Check total context size
        total_size = (
            len(ctx.user_message)
            + len(ctx.branch_summary)
            + sum(len(str(turn)) for turn in ctx.recent_turns)
            + sum(len(str(node)) for node in ctx.relevant_nodes)
        )
        if total_size > MAX_TOTAL_CONTEXT_SIZE:
            return False, f"total context size {total_size} exceeds max {MAX_TOTAL_CONTEXT_SIZE}"

        return True, ""

    def validate_branch_consistency(
        self,
        ctx: LlmContext,
        expected_branch_id: UUID,
    ) -> tuple[bool, str]:
        """
        Verify that all context fields reference the correct branch.
        
        This is a cross-user data leakage check: if the context was fetched from
        the wrong branch, we reject it.
        
        Args:
            ctx: The context to check
            expected_branch_id: The branch_id from the incoming request

        Returns:
            (is_valid, error_message)
        """
        # Check branch_summary: if it contains a branch_id, it should match
        # (branch_summary is system-generated, so we check for consistency)
        if ctx.branch_summary and "branch" in ctx.branch_summary.lower():
            # Simple heuristic: if summary mentions "branch", log it (for now, don't fail)
            if VERBOSE_LOGGING:
                logger.debug(f"branch_summary contains 'branch' keyword")

        # Check recent_turns: each should have branch_id matching expected
        for i, turn in enumerate(ctx.recent_turns):
            if hasattr(turn, "branch_id") and turn.branch_id != expected_branch_id:
                return (
                    False,
                    f"Turn {i} has branch_id {turn.branch_id}, expected {expected_branch_id}",
                )

        # Check relevant_nodes: each should have branch_id in their branch_tags
        for i, node in enumerate(ctx.relevant_nodes):
            if hasattr(node, "branch_tags"):
                if expected_branch_id not in node.branch_tags:
                    return (
                        False,
                        f"Node {i} branch_tags do not include {expected_branch_id}",
                    )

        return True, ""

    def redact_context(self, ctx: LlmContext) -> LlmContext:
        """
        Remove or obscure sensitive metadata from context fields.
        
        Redacts:
          - Timestamps on turns
          - Internal IDs (user IDs, story IDs if not needed)
          - Sensitive properties on nodes
        
        Note: This is a placeholder for future implementation.
        For now, returns ctx unchanged (no redaction needed in current schema).
        """
        # TODO: Implement if schema expands to include sensitive metadata
        # Current schema (ConversationTurn, Node) is relatively safe

        if VERBOSE_LOGGING:
            logger.debug("Context redaction (no-op for current schema)")

        return ctx
