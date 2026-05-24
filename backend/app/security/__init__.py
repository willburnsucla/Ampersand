"""
Prompt Security Module — Multi-layer defense against prompt injection, data leakage, and jailbreaking.

Public API:
  - PromptSecurityManager: Main orchestrator (call process_context)
  - SecurityException: Exception raised on validation failure

Internal components (imported by manager, not directly by consumers):
  - PromptSanitizer: Text cleaning
  - ContextValidator: Structure/boundary validation
  - InjectionDetector: Pattern-based detection

Usage:
    from app.security import PromptSecurityManager, SecurityException
    
    manager = PromptSecurityManager()
    try:
        sanitized_ctx = await manager.process_context(ctx, story_id, branch_id)
    except SecurityException as e:
        return HTTPException(status_code=400, detail="Invalid input")
"""
from __future__ import annotations

from app.security.manager import PromptSecurityManager, SecurityException

__all__ = [
    "PromptSecurityManager",
    "SecurityException",
]
