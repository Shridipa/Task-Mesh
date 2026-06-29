"""Integration tests for the TaskMesh FastAPI HTTP API and TaskMeshEngine."""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()
WORKER_SECRET = os.getenv("WORKER_SECRET", "taskmesh_secret")

from taskmesh.main import app  # noqa: E402

WORKER_HEADERS = {"X-Worker-Token": WORKER_SECRET, "X-Role": "worker"}
ADMIN_HEADERS = {"X-Role": "admin"}
DEV_HEADERS = {"X-Role": "developer"}
VIEWER_HEADERS = {"X-Role": "viewer"}

SAMPLE_JOB = {"job_type": "email", "payload": {"to": "user@example.com"}, "priority": 5, "tenant_id": "test_tenant"}

@pytest.fixture()
def client():
    # Database and Redis cleanup logic for isolation between tests
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://taskmesh:taskmesh_secret@localhost:5432/taskmesh",
    )
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        import psycopg2
        conn = psycopg2.connect(sync_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("TRUNCATE jobs, workers, events CASCADE;")
        conn.close()
    except Exception as e:
        print(f"Skipping PostgreSQL cleanup: {e}")

    try:
        import redis as redis_sync
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = redis_sync.from_url(redis_url)
        r.flushdb()
        r.close()
    except Exception as e:
        print(f"Skipping Redis cleanup: {e}")

    try:
        from sqlalchemy import create_engine
        from taskmesh.db import Base
        if db_url.startswith("sqlite"):
            sync_create_url = db_url.replace("sqlite+aiosqlite:///", "sqlite:///")
            eng = create_engine(sync_create_url)
            Base.metadata.create_all(eng)
            eng.dispose()
    except Exception as e:
        print(f"Skipping SQLite schema creation: {e}")

    with TestClient(app) as c:
        yield c

@pytest.mark.asyncio
async def test_create_job(client: TestClient):
    """Test job creation via POST /jobs/."""
    response = client.post("/jobs/", json=SAMPLE_JOB, headers=DEV_HEADERS)
    assert response.status_code == 201
    job_data = response.json()
    assert "id" in job_data
    assert isinstance(job_data["id"], str)
    assert job_data["job_type"] == SAMPLE_JOB["job_type"]
    assert job_data["tenant_id"] == SAMPLE_JOB["tenant_id"]
    assert job_data["status"] == "pending" # Initial status for a non-scheduled job
