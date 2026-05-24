"""
Security configuration — thresholds, patterns, token budgets.

Configurable by environment; defaults are balanced (not overly aggressive).
"""
from __future__ import annotations

import os
from typing import Final

# ── Size Limits ────────────────────────────────────────────────────────────

# Max length of sanitized user message (chars). TurnRequest already caps at 32KB,
# but we enforce a tighter limit to ensure predictable token budgets.
MAX_USER_MESSAGE_LENGTH: Final[int] = int(os.getenv("SECURITY_MAX_USER_MESSAGE_LENGTH", "10000"))

# Max length of branch summary (chars). System-generated, should be modest.
MAX_BRANCH_SUMMARY_LENGTH: Final[int] = int(os.getenv("SECURITY_MAX_BRANCH_SUMMARY_LENGTH", "2000"))

# Max number of recent turns to include in context.
MAX_RECENT_TURNS: Final[int] = int(os.getenv("SECURITY_MAX_RECENT_TURNS", "5"))

# Max number of relevant nodes to include in context.
MAX_RELEVANT_NODES: Final[int] = int(os.getenv("SECURITY_MAX_RELEVANT_NODES", "20"))

# Total combined size of context (user_message + summary + turns + nodes) in chars.
MAX_TOTAL_CONTEXT_SIZE: Final[int] = int(os.getenv("SECURITY_MAX_TOTAL_CONTEXT_SIZE", "20000"))

# ── Prompt Injection Detection Patterns ────────────────────────────────────

# Keywords that indicate potential prompt injection or jailbreak attempts.
# Heuristic-based; not exhaustive. Added patterns here when observed in the wild.
INJECTION_KEYWORDS: Final[list[str]] = [
    "system prompt",
    "system message",
    "ignore",
    "instructions",
    "override",
    "disregard",
    "forget",
    "pretend you",
    "you are now",
    "as an ai",
    "as a language model",
    "i jailbroke",
    "roleplay",
    "act as",
    "user wants",
    "bypass",
]

# Keywords that are suspicious only in combination with other patterns.
# (e.g., "ignore" + "rules" is worse than either alone)
SUSPICIOUS_PATTERNS: Final[list[tuple[str, ...]]] = [
    ("ignore", "rules"),
    ("ignore", "instructions"),
    ("forget", "story"),
    ("disregard", "character"),
    ("pretend", "character", "speaks"),
]

# Control characters to strip (except \n and \t).
CONTROL_CHARS_TO_REMOVE: Final[str] = "".join(
    chr(i) for i in range(0x00, 0x20) if i not in (0x0A, 0x09)  # except newline, tab
)

# ── Injection Scoring ──────────────────────────────────────────────────────

# Suspicion score threshold: if score >= this, raise SecurityException (fail-safe).
# If score is lower, log warning but allow (configurable via env).
INJECTION_SCORE_THRESHOLD: Final[float] = float(os.getenv("SECURITY_INJECTION_SCORE_THRESHOLD", "3.0"))

# Suspicion score for each matched keyword.
KEYWORD_SCORE_PER_MATCH: Final[float] = 1.0

# Bonus multiplier for pattern combinations.
PATTERN_MULTIPLIER: Final[float] = 1.5

# ── Behavior Flags ────────────────────────────────────────────────────────

# If True, reject input on high suspicion score. If False, log but allow (for dev/testing).
ENFORCE_INJECTION_REJECTION: Final[bool] = os.getenv("SECURITY_ENFORCE_INJECTION_REJECTION", "true").lower() in (
    "true",
    "1",
    "yes",
)

# If True, strip suspicious input; if False, raise exception. Only used if enforcing.
STRIP_SUSPICIOUS_CONTENT: Final[bool] = os.getenv("SECURITY_STRIP_SUSPICIOUS_CONTENT", "false").lower() in (
    "true",
    "1",
    "yes",
)

# If True, escape quotes/apostrophes (aggressive, breaks storytelling dialogue).
# If False, only remove control chars and normalize Unicode (recommended for creative writing).
# Escaping should happen at the Extractor level using proper JSON encoding, not here.
ESCAPE_QUOTES: Final[bool] = os.getenv("SECURITY_ESCAPE_QUOTES", "false").lower() in (
    "true",
    "1",
    "yes",
)

# ── Logging ───────────────────────────────────────────────────────────────

# If True, log all sanitization operations (verbose).
VERBOSE_LOGGING: Final[bool] = os.getenv("SECURITY_VERBOSE_LOGGING", "false").lower() in (
    "true",
    "1",
    "yes",
)
