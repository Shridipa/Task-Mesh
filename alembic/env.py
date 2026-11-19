"""Alembic environment configuration.

The migration context uses ``Base.metadata`` from ``src.taskmesh.db`` after
importing every ORM model, so ``alembic revision --autogenerate`` and
``alembic check`` compare against the real schema. The database URL always
comes from ``DATABASE_URL``; the async driver is converted to its synchronous
equivalent by :func:`taskmesh.config.to_sync_url`.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Ensure the repository root (and therefore ``src``) is importable.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from taskmesh.config import ConfigError, redact_url, to_sync_url
from taskmesh.db import (
    Base,
    models,  # noqa: F401  (registers the ORM models)
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Return the configured URL, failing clearly when it is missing."""
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url or url == "driver://user:pass@localhost/dbname":
        raise ConfigError(
            "DATABASE_URL is not set. Export it (for example "
            "postgresql+asyncpg://user:pass@host:5432/taskmesh) before running Alembic."
        )
    return url


def run_migrations_offline() -> None:
    """Emit SQL instead of executing it (``alembic upgrade head --sql``)."""
    context.configure(
        url=to_sync_url(_database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a synchronous connection."""
    raw_url = _database_url()
    if raw_url.split("://", 1)[0].startswith("sqlite"):
        raise ConfigError(
            "The TaskMesh migration history targets PostgreSQL. SQLite is a "
            "development/test backend and gets its schema from the ORM "
            "(AUTO_CREATE_SCHEMA=true or 'pytest'), not from Alembic."
        )

    sync_url = to_sync_url(raw_url)
    print(f"[alembic] connecting to {redact_url(sync_url)}")

    connectable = create_engine(sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
