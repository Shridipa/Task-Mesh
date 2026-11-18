"""Tests for explicit database URL and engine configuration."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from taskmesh.api.dependencies import create_database_engine


def test_postgres_url_creates_async_engine():
    engine = create_database_engine(
        "postgresql+asyncpg://taskmesh:secret@localhost:5432/taskmesh"
    )
    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "postgresql+asyncpg"
        assert engine.pool._pre_ping is True
    finally:
        import asyncio

        asyncio.run(engine.dispose())


def test_sqlite_url_creates_async_engine():
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "sqlite+aiosqlite"
    finally:
        import asyncio

        asyncio.run(engine.dispose())


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://taskmesh:secret@localhost:5432/taskmesh",
        "sqlite:///./taskmesh.db",
        "mysql+aiomysql://user:secret@localhost/taskmesh",
    ],
)
def test_unsupported_or_sync_database_drivers_fail_fast(database_url):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        create_database_engine(database_url)


def test_invalid_pool_settings_fail_fast(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "0")
    with pytest.raises(ValueError, match="pool settings"):
        create_database_engine(
            "postgresql+asyncpg://taskmesh:secret@localhost:5432/taskmesh"
        )
