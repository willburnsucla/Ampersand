"""
PromptSanitizer — Core text cleaning logic (minimalist approach for creative writing).

Philosophy: We preserve storytelling flexibility while removing only essential threats:
  - Remove control characters (null bytes, etc.) — true security risk
  - Normalize Unicode (homograph attacks) — true security risk
  - DO NOT escape quotes/apostrophes — breaks natural dialogue and storytelling
  
Quote/apostrophe escaping should happen at the Extractor level using proper JSON encoding,
not here in the sanitizer. This keeps text natural for authors while ensuring safe LLM prompts.

Methods:
  - sanitize_text(text: str) -> str: Remove control chars, normalize Unicode
  - remove_control_characters(text: str) -> str: Strip non-printable chars
  - escape_dangerous_chars(text: str) -> str: [DISABLED] Only called explicitly if needed
  - normalize_unicode(text: str) -> str: NFKC normalization (prevent homograph attacks)
  - truncate(text: str, max_length: int) -> str: Enforce size limit
"""
from __future__ import annotations

import logging
import unicodedata
from typing import Final

from app.security.config import (
    CONTROL_CHARS_TO_REMOVE,
    ESCAPE_QUOTES,
    MAX_USER_MESSAGE_LENGTH,
    VERBOSE_LOGGING,
)

logger = logging.getLogger(__name__)


class PromptSanitizer:
    """
    Text-level sanitization for prompts.
    
    Designed to be reusable (not specific to LlmContext).
    Can be used for any user-provided text destined for LLM or storage.
    """

    def sanitize_text(
        self,
        text: str,
        max_length: int = MAX_USER_MESSAGE_LENGTH,
        normalize: bool = True,
    ) -> str:
        """
        End-to-end sanitization: remove control chars, normalize Unicode, truncate.
        
        NOTE: We do NOT escape quotes/apostrophes here (too aggressive for storytelling).
        The Extractor should use proper JSON/prompt encoding when building the actual LLM prompt.

        Args:
            text: Raw user input
            max_length: Max output length (default: MAX_USER_MESSAGE_LENGTH)
            normalize: Whether to normalize Unicode (default: True)

        Returns:
            Sanitized text, safe for LLM consumption
        """
        if not text:
            return text

        # Step 1: Normalize Unicode (convert lookalikes to canonical form)
        if normalize:
            text = self.normalize_unicode(text)

        # Step 2: Remove control characters
        text = self.remove_control_characters(text)

        # Step 3: Truncate to max length
        text = self.truncate(text, max_length)

        return text

    def remove_control_characters(self, text: str) -> str:
        """
        Strip control characters (except \n, \t which are safe).
        
        Removes: \x00-\x08, \x0B-\x0C, \x0E-\x1F (null, bell, VT, FF, shift-out, etc.)
        Keeps: \x09 (tab), \x0A (newline), \x0D (carriage return)
        """
        if not text:
            return text

        result = "".join(c for c in text if c not in CONTROL_CHARS_TO_REMOVE)

        if VERBOSE_LOGGING and len(result) != len(text):
            logger.debug(f"Removed {len(text) - len(result)} control characters")

        return result

    def escape_dangerous_chars(self, text: str) -> str:
        """
        Escape quotes and backslashes (DISABLED for storytelling flexibility).
        
        This method is kept for backward compatibility but is NOT used by sanitize_text().
        If needed, call explicitly and only when you're sure escaping is safe.
        
        Quote escaping is too aggressive for creative writing dialogue (e.g., "Don't worry," she said.)
        The Extractor should use proper JSON encoding instead.
        """
        if not text:
            return text

        # Escape backslash first (so we don't double-escape)
        text = text.replace("\\", "\\\\")

        # Escape double quotes
        text = text.replace('"', '\\"')

        # Escape single quotes (for shell safety)
        text = text.replace("'", "\\'")

        if VERBOSE_LOGGING:
            logger.debug("Escaped dangerous characters (manual call)")

        return text

    def normalize_unicode(self, text: str) -> str:
        """
        Normalize Unicode to NFKC (Compatibility Decomposition, then Canonical Composition).
        
        Prevents homograph attacks where lookalike characters (e.g., Cyrillic 'А' vs Latin 'A')
        are used to trick the model or humans.
        """
        if not text:
            return text

        normalized = unicodedata.normalize("NFKC", text)

        if VERBOSE_LOGGING and normalized != text:
            logger.debug(f"Normalized Unicode: {repr(text[:50])} → {repr(normalized[:50])}")

        return normalized

    def truncate(self, text: str, max_length: int) -> str:
        """
        Truncate text to max_length characters.
        
        Does NOT add ellipsis (to avoid leaking truncation to the model as a prompt).
        """
        if len(text) <= max_length:
            return text

        truncated = text[:max_length]

        if VERBOSE_LOGGING:
            logger.debug(f"Truncated text from {len(text)} to {max_length} chars")

        return truncated
