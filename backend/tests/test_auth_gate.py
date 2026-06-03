"""
Unit tests for the Supabase auth gate (app.auth.supabase_gate).

Covers:
  - SupabaseAuthGate.verify(): signature, audience, expiry, and 'sub' handling
  - MockAuthGate: always returns the fixed dev user

These are pure-logic tests with no database, so they do NOT request the
db_session fixture and run without Docker. Tokens are minted with jose using a
known secret patched into settings, then fed back through verify().
"""
from __future__ import annotations

import time

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.auth.supabase_gate import (
    AuthenticationError,
    MockAuthGate,
    SupabaseAuthGate,
    UserContext,
    get_current_user,
)

_TEST_SECRET = "test-secret-do-not-use-in-prod"
_ALGO = "HS256"
_AUD = "authenticated"


# Factory for a default (valid) login token. Tests override one field at a time
# to make it bad and check the gate rejects it.
def _make_token(
    *,
    secret: str = _TEST_SECRET,
    sub: str | None = "user-123",
    aud: str | None = _AUD,
    email: str | None = "writer@ampersand.local",
    exp_offset: int = 3600,
) -> str:
    """Mint a JWT for tests. exp_offset is seconds from now (negative = expired)."""
    claims: dict = {"exp": int(time.time()) + exp_offset}
    if sub is not None:
        claims["sub"] = sub
    if aud is not None:
        claims["aud"] = aud
    if email is not None:
        claims["email"] = email
    return jwt.encode(claims, secret, algorithm=_ALGO)

# Setup
@pytest.fixture(autouse=True)
def _patch_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the gate at a known secret so tests don't depend on .env."""
    monkeypatch.setattr(
        "app.auth.supabase_gate.settings.supabase_jwt_secret", _TEST_SECRET
    )


# SupabaseAuthGate.verify() 
class TestSupabaseAuthGate:
    @pytest.fixture
    def gate(self) -> SupabaseAuthGate:
        return SupabaseAuthGate()

    async def test_valid_token_returns_user_context(self, gate: SupabaseAuthGate) -> None:
        """A well formed, correctly signed session token resolves to a UserContext."""
        # All tests follow same pattern of make token
        token = _make_token(sub="user-123", email="writer@ampersand.local")
        # Should it succeed?
        user = await gate.verify(token)
        assert isinstance(user, UserContext)
        assert user.user_id == "user-123"
        assert user.email == "writer@ampersand.local"

    async def test_token_without_email_is_allowed(self, gate: SupabaseAuthGate) -> None:
        """email is optional a token without it still resolves, email is None."""
        token = _make_token(email=None)
        user = await gate.verify(token)
        assert user.user_id == "user-123"
        assert user.email is None

    async def test_bad_signature_is_rejected(self, gate: SupabaseAuthGate) -> None:
        """A token signed with the wrong secret must be rejected (forgery)."""
        token = _make_token(secret="attacker-secret")
        with pytest.raises(AuthenticationError):
            await gate.verify(token)

    async def test_expired_token_is_rejected(self, gate: SupabaseAuthGate) -> None:
        """A token past its exp must be rejected jose enforces expiry."""
        token = _make_token(exp_offset=-10) 
        # For rejections raise AuthError
        with pytest.raises(AuthenticationError):
            await gate.verify(token)

    async def test_wrong_audience_is_rejected(self, gate: SupabaseAuthGate) -> None:
        """A correctly signed but non-session token (wrong aud) is rejected."""
        token = _make_token(aud="password-recovery")
        with pytest.raises(AuthenticationError):
            await gate.verify(token)

    async def test_missing_audience_is_rejected(self, gate: SupabaseAuthGate) -> None:
        """verify() requires aud=authenticated; a token with no aud is rejected."""
        token = _make_token(aud=None)
        with pytest.raises(AuthenticationError):
            await gate.verify(token)

    async def test_missing_sub_gives_clean_auth_error(self, gate: SupabaseAuthGate) -> None:
        """A signed token lacking 'sub' raises AuthenticationError, not a raw crash."""
        token = _make_token(sub=None)
        with pytest.raises(AuthenticationError, match="sub"):
            await gate.verify(token)

    async def test_garbage_string_is_rejected(self, gate: SupabaseAuthGate) -> None:
        """A non-JWT string is rejected as an AuthenticationError, not a 500."""
        with pytest.raises(AuthenticationError):
            await gate.verify("not-a-jwt")


# get_current_user() — the FastAPI dependency / HTTP boundary 
class TestGetCurrentUser:
    """
    get_current_user wraps the gate and converts an AuthenticationError into an
    HTTP 401. These tests drive that wrapper directly with a real
    SupabaseAuthGate patched in (bypassing the mock-mode default).
    """

    @pytest.fixture(autouse=True)
    def _use_real_gate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "app.auth.supabase_gate._gate", SupabaseAuthGate()
        )
    # Wrap token in proper format
    @staticmethod
    def _creds(token: str) -> HTTPAuthorizationCredentials:
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    # A valid, logged in user, can enter and is identified
    async def test_valid_token_passes_through(self) -> None:
        """A valid token resolves to the UserContext, no exception."""
        user = await get_current_user(self._creds(_make_token(sub="user-123")))
        assert user.user_id == "user-123"

    async def test_invalid_token_becomes_http_401(self) -> None:
        """An AuthenticationError is converted to a 401, not leaked as a 500."""
        # Confirm clean expected rejection instead of 500 error on bad jwt
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(self._creds("not-a-jwt"))
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"


# MockAuthGate 
class TestMockAuthGate:
    async def test_accepts_any_token_and_returns_fixed_user(self) -> None:
        """MockAuthGate ignores the token and returns the fixed dev user."""
        gate = MockAuthGate()
        user = await gate.verify("literally-anything")
        assert user.user_id == "mock-user-id"
        assert user.email == "dev@ampersand.local"
