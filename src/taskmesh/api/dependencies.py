"""Shared database and Redis dependencies for TaskMesh."""

from __future__ import annotations

import logging
import os
from typing import AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..db import Base
from ..db import models  # noqa: F401 - register ORM models with Base.metadata

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


def create_database_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine without silently changing backends.

    PostgreSQL is the production backend and must use asyncpg. SQLite remains
    available for local development and isolated tests.
    """
    url = make_url(database_url)
    driver = url.drivername

    if driver == "postgresql":
        raise ValueError(
            "DATABASE_URL must use the async PostgreSQL driver: "
            "postgresql+asyncpg://..."
        )
    if driver == "sqlite":
        raise ValueError(
            "DATABASE_URL must use the async SQLite driver: sqlite+aiosqlite://..."
        )
    if driver not in {"postgresql+asyncpg", "sqlite+aiosqlite"}:
        raise ValueError(
            "Unsupported DATABASE_URL driver. Use postgresql+asyncpg or sqlite+aiosqlite."
        )

    if driver == "postgresql+asyncpg":
        pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))

        if pool_size < 1 or max_overflow < 0 or pool_timeout < 1 or pool_recycle < 1:
            raise ValueError(
                "Database pool settings must be positive; DB_MAX_OVERFLOW may be zero."
            )

        return create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
        )

    # SQLite's async dialect uses a different pool implementation and does not
    # accept the PostgreSQL QueuePool sizing options.
    return create_async_engine(url, echo=False)


DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
engine = create_database_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_schema() -> None:
    """Create tables only for the SQLite development/test database.

    Production PostgreSQL schemas are managed exclusively by Alembic. This
    avoids application replicas racing to mutate the schema at startup.
    """
    if engine.url.get_backend_name() != "sqlite":
        logger.info(
            "Skipping automatic schema creation for %s; run 'alembic upgrade head'.",
            engine.url.get_backend_name(),
        )
        return

    logger.info("Creating SQLite development/test schema")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for each request."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Yield the shared Redis client."""
    yield redis_client
