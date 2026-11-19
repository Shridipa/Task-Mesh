"""Shared fixtures for the TaskMesh test suite."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import delete

from taskmesh.api.dependencies import create_schema, engine
from taskmesh.db import Base
from taskmesh.db.models import Job as OrmJob


def ensure_schema() -> None:
    """Create the schema once, then release the bootstrap loop's connections.

    Async database drivers bind connections to the event loop that opened them.
    Running the bootstrap in a throwaway loop and disposing the pool keeps later
    test loops (and ``TestClient`` lifecycles) from reusing connections that
    belong to a loop that no longer exists.
    """
    async def _bootstrap() -> None:
        # Start every run from an empty schema so stale rows from a previous
        # run cannot be picked up by the worker under test.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await create_schema()
        await engine.dispose()

    asyncio.run(_bootstrap())


def clear_pending_jobs() -> None:
    """Delete queued jobs so a worker under test only sees the test's own work."""
    async def _clear() -> None:
        async with engine.begin() as conn:
            await conn.execute(
                delete(OrmJob).where(
                    OrmJob.status.in_(["pending", "scheduled", "running"])
                )
            )
        await engine.dispose()

    asyncio.run(_clear())


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    ensure_schema()


@pytest.fixture(scope="module")
def clean_queue() -> None:
    """Module-level cleanup so background workers only see this module's jobs."""
    clear_pending_jobs()


@pytest.fixture(scope="session")
def database_url() -> str:
    return engine.url.render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def is_postgres(database_url: str) -> bool:
    return database_url.startswith("postgresql")
