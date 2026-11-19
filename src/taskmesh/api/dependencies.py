"""Database and Redis wiring shared by the API and the worker.

The engine is created once per process from :mod:`taskmesh.config`. Nothing in
this module rewrites ``DATABASE_URL``: whatever the operator configured is what
SQLAlchemy connects to. A PostgreSQL URL therefore stays PostgreSQL, and an
invalid or unreachable database fails loudly instead of quietly falling back to
SQLite.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from ..config import get_settings, redact_url
from ..db import Base
from ..db import models  # noqa: F401  (registers the ORM models on Base.metadata)

logger = logging.getLogger(__name__)

settings = get_settings()

DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url


def _engine_options() -> dict[str, Any]:
    """Pool configuration appropriate for the configured backend."""
    options: dict[str, Any] = {"echo": False, "future": True, "pool_pre_ping": True}
    if settings.environment == "test":
        # Async drivers bind connections to the loop that opened them. The test
        # suite (and Starlette's TestClient) uses several loops, so tests run
        # without a pool: every checkout gets a connection in the caller's loop.
        options["poolclass"] = NullPool
        return options
    if settings.is_sqlite:
        # A single in-memory database must stay on one connection, otherwise
        # every checkout would see an empty schema.
        if ":memory:" in DATABASE_URL:
            options["poolclass"] = StaticPool
        return options
    options.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
    )
    return options


#: Process-wide async engine. Logged redacted so credentials never leak.
engine = create_async_engine(DATABASE_URL, **_engine_options())
logger.debug("Database engine created for %s", redact_url(DATABASE_URL))

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

redis_client = Redis.from_url(REDIS_URL)


async def create_schema() -> None:
    """Create missing tables when ``AUTO_CREATE_SCHEMA`` allows it.

    Production deployments are expected to run ``alembic upgrade head`` and
    leave ``AUTO_CREATE_SCHEMA`` disabled, so schema changes stay versioned.
    """
    if not settings.auto_create_schema:
        logger.info(
            "AUTO_CREATE_SCHEMA is disabled; apply migrations with 'alembic upgrade head'"
        )
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.debug("Schema ensured for %s", redact_url(DATABASE_URL))


async def database_ready() -> bool:
    """Return True when a trivial query succeeds against the configured database."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, OSError) as exc:
        logger.warning(
            "Database readiness check failed for %s: %s",
            redact_url(DATABASE_URL),
            type(exc).__name__,
        )
        return False


async def redis_ready() -> bool:
    """Return True when Redis answers PING."""
    try:
        await redis_client.ping()
        return True
    except Exception as exc:  # noqa: BLE001 - redis-py raises many error types
        logger.warning("Redis readiness check failed: %s", type(exc).__name__)
        return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for each request."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Yield the shared Redis client."""
    yield redis_client


async def dispose_engine() -> None:
    """Release pooled database connections.

    Async drivers bind connections to the event loop that opened them, so this
    must be awaited in the loop that is shutting down.
    """
    await engine.dispose()


async def dispose_redis() -> None:
    """Close the shared Redis client."""
    try:
        await redis_client.aclose()
    except Exception as exc:  # noqa: BLE001 - closing must not mask shutdown
        logger.debug("Redis client close raised %s", type(exc).__name__)
