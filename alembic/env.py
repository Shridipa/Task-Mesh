"""Alembic environment configuration.

This file sets up the migration context so that ``alembic`` can locate the
SQLAlchemy ``MetaData`` object that contains our model definitions.  The
``Base`` class (and thus ``Base.metadata``) lives in ``src.taskmesh.db.base``.
"""

from __future__ import with_statement
import os
from logging.config import fileConfig

from sqlalchemy import pool
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ----------------------------------------------------------------------
# add your model's MetaData object here for 'autogenerate' support
# ----------------------------------------------------------------------
# Import the Base metadata from the project's engine module.
# The import path must be importable when alembic runs (i.e. the project
# root is on PYTHONPATH).  We also make ``DATABASE_URL`` overridable via an
# environment variable – this matches the Docker container's runtime config.

sys_path_added = False
if "PYTHONPATH" not in os.environ:
    # Ensure the repository root is on the path when alembic runs.
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    sys_path_added = True

# Import all models to ensure metadata is populated
from src.taskmesh.db import Base  # noqa: E402

target_metadata = Base.metadata

# ----------------------------------------------------------------------
# other configuration settings
# ----------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    In this mode, Alembic does not need a DB connection; it just emits the
    SQL statements to the script output.  The URL is taken from the
    ``DATABASE_URL`` environment variable (or from the ``alembic.ini``
    placeholder if not set).
    """
    url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    We use a *synchronous* PostgreSQL engine for Alembic because the async
    driver (``+asyncpg``) cannot be used in the migration context. If the
    ``DATABASE_URL`` contains ``+asyncpg`` we replace it with ``+psycopg2``.
    """
    # Transform async URL to a sync one for Alembic
    raw_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    sync_url = raw_url.replace("+asyncpg", "+psycopg2") if raw_url else None
    if not sync_url:
        raise RuntimeError("DATABASE_URL not set for Alembic migrations")

    from sqlalchemy import create_engine
    connectable = create_engine(sync_url, poolclass=pool.NullPool)


    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
