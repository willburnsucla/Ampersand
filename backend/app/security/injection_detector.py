"""Pattern-based detection for prompt injection and jailbreak attempts."""
from __future__ import annotations

import logging
from typing import Final

from app.security.config import (
    INJECTION_KEYWORDS,
    INJECTION_SCORE_THRESHOLD,
    KEYWORD_SCORE_PER_MATCH,
    PATTERN_MULTIPLIER,
    SUSPICIOUS_PATTERNS,
    VERBOSE_LOGGING,
)

logger = logging.getLogger(__name__)


class InjectionDetector:
    """
    Pattern-based detection for prompt injection and jailbreak attempts.
    
    Heuristic-based scoring:
      - Each matched keyword scores KEYWORD_SCORE_PER_MATCH points
      - Each matched pattern combination scores PATTERN_MULTIPLIER × keyword score
      - Score >= INJECTION_SCORE_THRESHOLD is flagged as high-confidence injection
    
    Not a guarantee (can have false positives/negatives), but catches obvious attempts.
    """

    def detect_injection_attempt(
        self,
        text: str,
        threshold: float = INJECTION_SCORE_THRESHOLD,
    ) -> tuple[bool, float, list[str]]:
        """
        Detect if text contains injection or jailbreak patterns.

        Args:
            text: Text to analyze
            threshold: Suspicion score threshold (default: INJECTION_SCORE_THRESHOLD)

        Returns:
            (is_suspected, score, matched_keywords)
            - is_suspected: True if score >= threshold
            - score: Suspicion score (float)
            - matched_keywords: List of keywords that triggered the score
        """
        score, matched = self.score_suspicion(text)

        is_suspected = score >= threshold

        if VERBOSE_LOGGING:
            logger.debug(
                f"Injection detection: score={score:.1f}, threshold={threshold}, "
                f"suspected={is_suspected}, matched={matched}"
            )

        return is_suspected, score, matched

    def score_suspicion(self, text: str) -> tuple[float, list[str]]:
        """
        Score text for prompt injection/jailbreak suspicion.

        Returns:
            (total_score, matched_keywords)
        """
        if not text:
            return 0.0, []

        text_lower = text.lower()
        matched_keywords: list[str] = []
        score: float = 0.0

        # Step 1: Match individual keywords
        for keyword in INJECTION_KEYWORDS:
            if keyword in text_lower:
                matched_keywords.append(keyword)
                score += KEYWORD_SCORE_PER_MATCH

        # Step 2: Match suspicious patterns (combinations)
        for pattern in SUSPICIOUS_PATTERNS:
            # All words in the pattern must appear in the text (in any order)
            if all(word in text_lower for word in pattern):
                # Pattern matched; apply multiplier
                score += len(pattern) * KEYWORD_SCORE_PER_MATCH * PATTERN_MULTIPLIER
                matched_keywords.append(f"pattern: {' + '.join(pattern)}")

        return score, matched_keywords

    def extract_keywords(self, text: str) -> list[str]:
        """
        Extract all injection keywords found in text (lower-case matching).

        Returns:
            List of keywords from INJECTION_KEYWORDS that appear in text
        """
        if not text:
            return []

        text_lower = text.lower()
        found = [keyword for keyword in INJECTION_KEYWORDS if keyword in text_lower]

        return found
