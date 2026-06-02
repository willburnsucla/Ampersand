"""
AuthGate — T-013. Adapter over Supabase SDK.

Sole point of contact with Supabase on the backend.
Verifies JWT, resolves to internal UserContext, attaches to FastAPI request state.

Two implementations in one file (architectural invariant #7):
  - SupabaseAuthGate — real, verifies against Supabase JWT
  - MockAuthGate  — accepts any token, returns a fixed user (used by T-004 dev-mock)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError
from pydantic import BaseModel

from app.core.config import settings


class UserContext(BaseModel):
    user_id: str
    email: str | None = None


class AuthenticationError(Exception):
    """Raised by AuthGate implementations when JWT verification fails."""


class AuthGate(ABC):
    @abstractmethod
    async def verify(self, jwt: str) -> UserContext: ...


# Supabase implementation 
class SupabaseAuthGate(AuthGate):
    """Verifies JWTs against Supabase's JWT secret."""

    async def verify(self, token: str) -> UserContext:
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except JWTError as exc:
            raise AuthenticationError(f"Supabase JWT verification failed: {exc}") from exc

        # jose only checks aud when it's present
        if payload.get("aud") != "authenticated":
            raise AuthenticationError("token has wrong or missing audience")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("token missing 'sub' claim")
        return UserContext(user_id=user_id, email=payload.get("email"))


# Mock implementation 
class MockAuthGate(AuthGate):
    """Accepts any token and returns a fixed dev user. Never use in production."""

    MOCK_USER = UserContext(
        user_id="mock-user-id",
        email="dev@ampersand.local",
    )

    async def verify(self, jwt: str) -> UserContext:  # noqa: ARG002
        return self.MOCK_USER


# FastAPI dependency 
_bearer = HTTPBearer(auto_error=True)
_gate: AuthGate = MockAuthGate() if settings.is_mock else SupabaseAuthGate()


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
