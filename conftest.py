"""Root conftest.py — sets environment variables and test config before any module is imported.

Tests always run against an explicitly configured database. By default that is a
local SQLite file; set ``TEST_DATABASE_URL`` to run the same suite against a real
PostgreSQL instance (see ``tests/test_postgres.py`` and the README).
"""

from __future__ import annotations

import asyncio
import os
import sys

# Must be set BEFORE any taskmesh/backend modules are imported so that the
# module-level engine initialisation picks up the right URLs.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL") or "sqlite+aiosqlite:///./test.db",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("WORKER_SECRET", "taskmesh_secret")
os.environ.setdefault("AUTH_JWT_SECRET", "test-jwt-secret-not-for-production-use")
os.environ.setdefault(
    "AUTH_API_KEYS",
    "test-admin-key:admin:default,"
    "test-developer-key:developer:default,"
    "test-viewer-key:viewer:default",
)

# TaskMesh uses asyncio-only dependencies (asyncpg, FastAPI). Force asyncio.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def pytest_addoption(parser):
    parser.addoption(
        "--anyio-backend",
        default="asyncio",
        help="Force anyio backend (asyncio only supported)",
    )


def pytest_configure(config):
    # Ensure anyio only uses asyncio, never trio.
    os.environ.setdefault("ANYIO_BACKEND", "asyncio")
