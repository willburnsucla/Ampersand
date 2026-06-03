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

import httpx
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
    """
    Verifies Supabase JWTs.

    Supabase projects sign tokens either asymmetrically (ES256, the current
    default — verified with the project's public JWKS) or with the legacy
    symmetric secret (HS256). We pick the path by the token's `alg` header and
    fall back to HS256 so either scheme works.
    """

    # Cached JWKS keyed by `kid`. Fetched once on first asymmetric token.
    _jwks: dict[str, dict] = {}

    async def verify(self, token: str) -> UserContext:
        try:
            alg = jwt.get_unverified_header(token).get("alg")
        except JWTError as exc:
            raise AuthenticationError(f"malformed token: {exc}") from exc

        if alg == "HS256":
            payload = self._decode_hs256(token)
        else:
            payload = await self._decode_asymmetric(token, alg)

        # jose only checks aud when it's present
        if payload.get("aud") != "authenticated":
            raise AuthenticationError("token has wrong or missing audience")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("token missing 'sub' claim")
        return UserContext(user_id=user_id, email=payload.get("email"))

    def _decode_hs256(self, token: str) -> dict:
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except JWTError as exc:
            raise AuthenticationError(f"HS256 verification failed: {exc}") from exc

    async def _decode_asymmetric(self, token: str, alg: str | None) -> dict:
        kid = jwt.get_unverified_header(token).get("kid")
        key = await self._get_signing_key(kid)
        try:
            return jwt.decode(
                token,
                key,
                algorithms=[alg] if alg else ["ES256", "RS256"],
                audience="authenticated",
            )
        except JWTError as exc:
            raise AuthenticationError(f"{alg} verification failed: {exc}") from exc

    async def _get_signing_key(self, kid: str | None) -> dict:
        if kid and kid in self._jwks:
            return self._jwks[kid]

        if not settings.supabase_url:
            raise AuthenticationError("SUPABASE_URL not set; cannot fetch JWKS")

        url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                keys = resp.json().get("keys", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise AuthenticationError(f"could not fetch JWKS: {exc}") from exc

        self._jwks = {k["kid"]: k for k in keys if "kid" in k}

        if kid and kid in self._jwks:
            return self._jwks[kid]
        raise AuthenticationError(f"no signing key for kid={kid}")


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
