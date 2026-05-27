"""Main orchestrator for prompt security, delegates to sanitizer, validator, and detector.

process_context sanitizes and validates LlmContext, raises SecurityException on failure.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from app.security.context_validator import ContextValidator
from app.security.injection_detector import InjectionDetector
from app.security.prompt_sanitizer import PromptSanitizer

if TYPE_CHECKING:
    from app.services.extractor import LlmContext

logger = logging.getLogger(__name__)


class SecurityException(Exception):
    """
    Raised when prompt security validation fails.
    
    Includes a sanitized message (safe to return to client without leaking internals).
    """

    def __init__(self, message: str, *, sanitized_message: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.sanitized_message = sanitized_message or "Invalid input"


class PromptSecurityManager:
    """
    Multi-layer prompt security orchestrator.
    
    Workflow:
      1. Sanitize user_message (PromptSanitizer)
      2. Detect injection attempts (InjectionDetector)
      3. Validate LlmContext structure and boundaries (ContextValidator)
      4. Validate branch consistency (prevent cross-user leakage)
      5. Return sanitized context or raise SecurityException
    """

    def __init__(self) -> None:
        self.sanitizer = PromptSanitizer()
        self.validator = ContextValidator()
        self.detector = InjectionDetector()

    async def process_context(
        self,
        ctx: LlmContext,
        story_id: UUID,
        branch_id: UUID,
    ) -> LlmContext:
        """
        Process (sanitize + validate) an LlmContext before passing to Extractor.

        Args:
            ctx: The LlmContext from route handler
            story_id: Expected story_id (from request)
            branch_id: Expected branch_id (from request)

        Returns:
            Sanitized and validated LlmContext

        Raises:
            SecurityException: If any validation fails
        """
        logger.debug(f"Processing context: story_id={story_id}, branch_id={branch_id}")

        # Step 1: Detect injection in raw user_message
        is_injection, score, matched = self.detector.detect_injection_attempt(ctx.user_message)
        if is_injection:
            msg = f"Potential prompt injection detected (score={score:.1f}, patterns={matched})"
            logger.warning(msg)
            raise SecurityException(
                msg,
                sanitized_message="Your input contains suspicious patterns. Please try again.",
            )

        # Step 2: Sanitize user_message
        ctx.user_message = self.sanitizer.sanitize_text(ctx.user_message)

        # Step 3: Validate LlmContext structure and boundaries
        is_valid, err_msg = self.validator.validate_llm_context(ctx, branch_id)
        if not is_valid:
            logger.warning(f"Context validation failed: {err_msg}")
            raise SecurityException(
                err_msg,
                sanitized_message="Context is invalid. Please try again.",
            )

        # Step 4: Redact sensitive metadata
        ctx = self.validator.redact_context(ctx)

        logger.debug(f"Context processing succeeded (score={score:.1f})")
        return ctx
