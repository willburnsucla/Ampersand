"""Test fixtures: a throwaway Postgres (testcontainers) and a per-test session
that rolls back after each test, so tests are isolated."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

import app.domain.orm_v2  # noqa: F401  (registers v2 tables on Base.metadata)
from app.core.db import Base


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
