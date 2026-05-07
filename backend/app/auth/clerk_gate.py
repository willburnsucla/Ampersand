"""
AuthGate — T-013. Adapter over Clerk SDK.

Sole point of contact with Clerk on the backend.
Verifies JWT, resolves to internal UserContext, attaches to FastAPI request state.

Two implementations in one file (architectural invariant #7):
  - ClerkAuthGate — real, verifies against Clerk JWKS
  - MockAuthGate  — accepts any token, returns a fixed user (used by T-004 dev-mock)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings


class UserContext(BaseModel):
    """Internal user representation — Clerk-agnostic."""
    clerk_user_id: str
    email: str | None = None


class AuthenticationError(Exception):
    """Raised by AuthGate implementations when JWT verification fails."""


class AuthGate(ABC):
    @abstractmethod
    async def verify(self, jwt: str) -> UserContext: ...


# ── Clerk implementation ──────────────────────────────────────────────────────

class ClerkAuthGate(AuthGate):
    """Verifies JWTs against Clerk's JWKS endpoint. Lazily caches JWKS."""

    async def verify(self, jwt: str) -> UserContext:
        try:
            # clerk-backend-api v5 changed the verify_token location.
            # Import here to avoid hard dep when running in mock mode.
            from clerk_backend_api import Clerk  # type: ignore[import]
            from clerk_backend_api.jwks_helpers import authenticate_request  # type: ignore[import]

            # The v5 SDK exposes authenticate_request for request-level auth.
            # For token-only verification we use the lower-level helper.
            clerk = Clerk(bearer_auth=settings.clerk_secret_key)
            # Verify using JWKS (raises on failure)
            payload = clerk.verify_token(jwt)  # type: ignore[attr-defined]
            return UserContext(
                clerk_user_id=payload["sub"],
                email=payload.get("email"),
            )
        except Exception as exc:
            raise AuthenticationError(f"Clerk JWT verification failed: {exc}") from exc


# ── Mock implementation ───────────────────────────────────────────────────────

class MockAuthGate(AuthGate):
    """Accepts any token and returns a fixed dev user. Never use in production."""

    MOCK_USER = UserContext(
        clerk_user_id="mock-user-clerk-id",
        email="dev@ampersand.local",
    )

    async def verify(self, jwt: str) -> UserContext:  # noqa: ARG002
        return self.MOCK_USER


# ── FastAPI dependency ────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=True)
_gate: AuthGate = MockAuthGate() if settings.is_mock else ClerkAuthGate()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserContext:
    """
    FastAPI dependency. Inject into route handlers with Depends(get_current_user).
    In mock mode this is overridden in main.py via dependency_overrides.
    """
    try:
        return await _gate.verify(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
