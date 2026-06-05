"""Test fixtures: a throwaway Postgres (testcontainers) and a per-test session
that rolls back after each test, so tests are isolated."""
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

# pin mock mode before importing app modules, so the fail-closed real-mode default
# does not demand real secrets during tests
os.environ.setdefault("AMPERSAND_BACKEND_MODE", "mock")
# pin the extractor to the deterministic mock so tests never hit a real llm, even when a
# local .env sets EXTRACTOR_BACKEND=gemini for manual runs
os.environ.setdefault("EXTRACTOR_BACKEND", "mock")

import app.domain.orm_v2  # noqa: F401, E402  (registers v2 tables on Base.metadata)
from app.core.db import Base  # noqa: E402


@pytest.fixture(scope="session")
def _postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest_asyncio.fixture(scope="session")
async def _engine(_postgres):
    url = _postgres.get_connection_url().replace("+psycopg2", "+asyncpg")
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_engine):
    conn = await _engine.connect()
    txn = await conn.begin()
    maker = async_sessionmaker(bind=conn, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        await session.close()
        await txn.rollback()
        await conn.close()
