"""PostgreSQL integration tests.

These run only when the suite is pointed at a real PostgreSQL instance, e.g.::

    TEST_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/taskmesh pytest

They cover what SQLite cannot: migrations, SKIP LOCKED leasing under
concurrency and durability across engine instances.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from taskmesh.api.dependencies import engine
from taskmesh.engine import TaskMeshEngine
from taskmesh.models import JobCreate
from taskmesh.worker import run_worker

pytestmark = pytest.mark.skipif(
    engine.url.get_backend_name() != "postgresql",
    reason="set TEST_DATABASE_URL to a PostgreSQL URL to run these tests",
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ALEMBIC_HEAD_REVISION = "20240626000007"


def _status(job: dict) -> str:
    return getattr(job["status"], "value", job["status"])


def test_the_suite_is_actually_running_against_postgres():
    assert engine.url.get_backend_name() == "postgresql"


@pytest.mark.asyncio
async def test_jobs_persist_across_engine_instances():
    first = TaskMeshEngine()
    created = await first.create_job(
        JobCreate(
            job_type="text.process", payload={"text": "durable"}, tenant_id="pg-durable"
        )
    )

    second = TaskMeshEngine()
    stored = await second.get_job(created["id"])

    assert stored is not None
    assert stored["id"] == created["id"]
    assert stored["payload"] == {"text": "durable"}

    # Leave no pending work behind for the other tests in this module.
    await second.complete_job(created["id"], {"words": 1})


@pytest.mark.asyncio
async def test_concurrent_workers_never_lease_the_same_job(clean_queue):
    engine_api = TaskMeshEngine()
    created = [
        await engine_api.create_job(
            JobCreate(job_type="text.process", payload={"text": f"job {i}"}, tenant_id="pg")
        )
        for i in range(6)
    ]
    created_ids = {job["id"] for job in created}

    async def lease(worker: str) -> list[str]:
        leased: list[str] = []
        for _ in range(6):
            job = await engine_api.lease_next_job(worker, tenant_id="pg")
            if job is None:
                break
            leased.append(job["id"])
        return leased

    batches = await asyncio.gather(lease("worker-a"), lease("worker-b"))

    leased_ids = [job_id for batch in batches for job_id in batch]
    assert len(leased_ids) == len(set(leased_ids)), "a job was leased twice"
    assert set(leased_ids) <= created_ids


@pytest.mark.asyncio
async def test_worker_executes_a_job_on_postgres(clean_queue):
    engine_api = TaskMeshEngine()
    created = await engine_api.create_job(
        JobCreate(job_type="text.process", payload={"text": "Hello worker. Done!"}, tenant_id="pg")
    )

    handled = await run_worker(max_jobs=1)

    assert handled == 1
    stored = await engine_api.get_job(created["id"])
    assert _status(stored) == "completed"
    assert stored["result"]["words"] == 3
    assert stored["worker_id"]


@pytest.mark.asyncio
async def test_health_query_works_through_the_async_engine():
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT 1"))).scalar() == 1


def _maintenance_url() -> str:
    url = engine.url.set(database="postgres")
    return url.render_as_string(hide_password=False).replace("postgresql+asyncpg", "postgresql")


def _run_alembic(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_migrations_apply_to_a_clean_postgres_database():
    import psycopg2

    scratch = f"taskmesh_migration_{uuid.uuid4().hex[:8]}"
    admin = psycopg2.connect(_maintenance_url())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{scratch}"')

        async_url = engine.url.set(database=scratch).render_as_string(hide_password=False)
        try:
            upgrade = _run_alembic(async_url, "upgrade", "head")
            assert upgrade.returncode == 0, upgrade.stderr + upgrade.stdout

            check = _run_alembic(async_url, "check")
            assert check.returncode == 0, check.stdout + check.stderr

            conn = psycopg2.connect(
                async_url.replace("postgresql+asyncpg", "postgresql")
            )
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT version_num FROM alembic_version")
                    assert cur.fetchone()[0] == ALEMBIC_HEAD_REVISION
                    cur.execute(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name = 'jobs' AND column_name = 'id'"
                    )
                    assert cur.fetchone()[0] == "character varying"
            finally:
                conn.close()
        finally:
            with admin.cursor() as cur:
                cur.execute(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)')
    finally:
        admin.close()
