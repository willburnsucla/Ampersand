"""Core text cleaning for prompts, minimalist for creative writing.

Strips control characters and normalizes Unicode (NFKC) so homograph attacks
get folded out. Quote and apostrophe escaping happens at the Extractor level
via JSON encoding, not here, so dialogue stays readable for the writer.
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
        """End-to-end sanitization, removes control chars, normalizes Unicode, truncates to max_length.

        Quotes and apostrophes are intentionally preserved; the Extractor JSON encodes them at prompt build time.
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
