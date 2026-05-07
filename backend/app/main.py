"""
FastAPI app factory.

Wires together:
  - CORS middleware
  - API router (route handlers)
  - SSE router (EventBroadcaster + SSE endpoint)
  - Mock mode overrides (dependency_overrides for InMemory repos + MockAuthGate)

All real initialization (DB engine, JWKS cache warm-up) is deferred to lifespan.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    if not settings.is_mock:
        # Real mode: warm DB pool, JWKS cache, etc.
        pass
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────────
    if not settings.is_mock:
        from app.core.db import engine
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ampersand API",
        version="0.1.0",
        description="Story-development IDE backend",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Mock mode: override auth to skip real Clerk JWT verification ──────────
    if settings.is_mock:
        from app.auth.clerk_gate import MockAuthGate, UserContext, get_current_user

        mock_user = UserContext(clerk_user_id="mock-user-clerk-id", email="dev@ampersand.local")
        app.dependency_overrides[get_current_user] = lambda: mock_user

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.api.router import router as api_router
    from app.broadcast.sse import sse_router

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(sse_router, prefix="/api/v1")

    return app


app = create_app()
