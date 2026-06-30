import os
import uuid

import pytest
from taskmesh.engine import TaskMeshEngine
from taskmesh.models import JobCreate, JobStatus
from taskmesh.db.dependencies import create_schema

# Use a dummy redis that records published messages
class DummyRedis:
    def __init__(self):
        self.published = []
    async def publish(self, channel, message):
        self.published.append((channel, message))
    async def pipeline(self, transaction=True):
        # simple no-op context manager returning self with needed methods
        return self
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def execute(self):
        return []

dummy_redis = DummyRedis()

@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    # Ensure SQLite DB file in a temp directory
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    # Patch the redis client used by the engine
    monkeypatch.setattr("taskmesh.engine.redis_client", dummy_redis)
    # Create schema
    await create_schema()
    yield

@pytest.mark.asyncio
async def test_create_job_and_fetch():
    engine = TaskMeshEngine()
    job_req = JobCreate(
        job_type="email",
        payload={"to": "user@example.com"},
        priority=5,
        tenant_id="test",
        max_retries=2,
    )
    created = await engine.create_job(job_req)
    assert created["job_type"] == "email"
    assert created["tenant_id"] == "test"
    assert created["status"] == JobStatus.PENDING.value
    # Retrieve same job
    fetched = await engine.get_job(created["id"])
    assert fetched == created
    # List jobs returns at least this one
    jobs = await engine.list_jobs(tenant_id="test")
    assert any(j["id"] == created["id"] for j in jobs)
    # Verify a log was published
    assert any(chan == "taskmesh_logs" for chan, _ in dummy_redis.published)

@pytest.mark.asyncio
async def test_idempotent_job_creation():
    engine = TaskMeshEngine()
    key = str(uuid.uuid4())
    job_req = JobCreate(
        job_type="email",
        payload={"to": "a@b.com"},
        tenant_id="idem",
        idempotency_key=key,
    )
    first = await engine.create_job(job_req)
    second = await engine.create_job(job_req)
    assert first["id"] == second["id"]
