"""
InjectionDetector — Detection for prompt injection and jailbreak attempts.

Supports both ML-based and heuristic-based detection:
  - ML-based: Uses pre-trained logistic regression classifier (if model available)
  - Heuristic-based: Pattern matching fallback (always available)

Methods:
  - detect_injection_attempt(text: str) -> tuple[bool, float, list[str]]: Check for suspicion
  - score_suspicion(text: str) -> tuple[float, list[str]]: Return score + matched patterns
  - extract_keywords(text: str) -> list[str]: Find matched keywords in text
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from app.security.config import (
    INJECTION_KEYWORDS,
    INJECTION_SCORE_THRESHOLD,
    KEYWORD_SCORE_PER_MATCH,
    PATTERN_MULTIPLIER,
    SUSPICIOUS_PATTERNS,
    VERBOSE_LOGGING,
)

if TYPE_CHECKING:
    from app.security.ml_classifier import MLInjectionClassifier

logger = logging.getLogger(__name__)


class InjectionDetector:
    """
    Hybrid detection for prompt injection and jailbreak attempts.

    Attempts ML-based classification first (if model available). Falls back to
    heuristic pattern matching if ML fails or is not configured.

    ML scoring: 0-5 scale where higher = more suspicious
    Heuristic scoring: Sum of matched keywords + pattern combinations
    """

    def __init__(self, ml_classifier: Optional[MLInjectionClassifier] = None):
        """Initialize detector with optional ML classifier.

        Args:
            ml_classifier: Optional pre-trained ML classifier for injection detection.
                          If None, uses heuristic pattern matching only.
        """
        self.ml_classifier = ml_classifier

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

        Attempts ML-based classification first (if available). Falls back to
        heuristic pattern matching if ML fails.

        Returns:
            (total_score, matched_keywords_or_method)
            - total_score: 0-5 scale (higher = more suspicious)
            - matched_keywords_or_method: List of matched patterns or detection method
        """
        if not text:
            return 0.0, []

        # Try ML-based detection first
        if self.ml_classifier:
            ml_score = self.ml_classifier.score(text)
            if ml_score is not None:
                if VERBOSE_LOGGING:
                    logger.debug(f"Using ML classifier: score={ml_score:.2f}")
                return ml_score, ["detection_method: ML"]

        # Fall back to heuristic scoring
        return self._score_suspicion_heuristic(text)

    def _score_suspicion_heuristic(self, text: str) -> tuple[float, list[str]]:
        """
        Score text using heuristic pattern matching (keyword detection).

        Returns:
            (total_score, matched_keywords)
        """
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

        if VERBOSE_LOGGING and matched_keywords:
            logger.debug(f"Heuristic detection: score={score:.1f}, matched={matched_keywords}")

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
