"""Root conftest.py — sets environment variables and test config before any module is imported."""
from __future__ import annotations

import asyncio
import os
import sys

# Must be set BEFORE any taskmesh/backend modules are imported so that the
# module-level engine initialisation picks up the right URLs.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://taskmesh:taskmesh_secret@localhost:5432/taskmesh")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("WORKER_SECRET", "taskmesh_secret")

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

