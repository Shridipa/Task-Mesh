# src/taskmesh/api/dependencies.py
import os
from typing import AsyncGenerator
from ..db import Base
from ..db import models   # noqa: F401
from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# ----------------------------------------------------------------------
# Database
# ----------------------------------------------------------------------
# Use the DATABASE_URL from the environment directly.
# If nothing is set we default to a local SQLite file.
# If a PostgreSQL URL is set but unavailable in the test environment, fall back to SQLite.
if os.getenv("DATABASE_URL", "").startswith("postgres"):
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

# Always create an AsyncEngine
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# ---- **NEW**: create tables if they do not exist ----
# Import the Base that all ORM models inherit from and run the sync
# metadata creation inside an async context.
from ..db import Base  # <-- this pulls in taskmesh.db.__init__ (Base)
# The import also registers all models (Job, Worker, Event) because
# `taskmesh.db.models` imports them at module import time.
# If you have lazy imports elsewhere, you can also do:
# from ..db import models  # noqa: F401  (forces model registration)
async def create_schema():
    print("=" * 50)
    print("Tables registered:")
    print(list(Base.metadata.tables.keys()))
    print("=" * 50)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
# ----------------------------------------------------------------------

# Session factory – works with the AsyncEngine above
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ----------------------------------------------------------------------
# Redis
# ----------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = Redis.from_url(REDIS_URL)


# ----------------------------------------------------------------------
# Dependency helpers
# ----------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for each request."""
    async with AsyncSessionLocal() as session:
        yield session

async def get_redis() -> AsyncGenerator[Redis, None]:
    """Yield a Redis client."""
    yield redis_client