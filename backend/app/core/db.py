"""
Async SQLAlchemy engine, session factory, and Base declarative class.
All DB access goes through Repository modules — never import get_db into route handlers.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """All ORM models inherit from this."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for DB sessions.
    Used ONLY by Repository constructors — never injected into route handlers directly.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
