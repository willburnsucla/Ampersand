"""
Alembic env.py — uses sync psycopg2 driver (Alembic does not support asyncpg natively).
Imports all ORM models so autogenerate can see the full schema.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make app importable when running alembic from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.core.config import settings  # noqa: E402
from app.core.db import Base  # noqa: E402

# Import all ORM models so autogenerate picks them up
import app.domain.orm  # noqa: E402, F401

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return settings.sync_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection needed, emits SQL)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (real DB connection)."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
