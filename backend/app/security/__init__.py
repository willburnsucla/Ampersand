"""Multi-layer defense against prompt injection, data leakage, and jailbreaking.

PromptSecurityManager.process_context is the public entrypoint and raises
SecurityException on validation failure. Internals (sanitizer, validator,
detector) are not for direct import.
"""
from __future__ import annotations

from app.security.manager import PromptSecurityManager, SecurityException

__all__ = [
    "PromptSecurityManager",
    "SecurityException",
]
