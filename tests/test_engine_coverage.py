"""Engine-level tests: persistence, leasing, lifecycle and ownership."""

from __future__ import annotations

import uuid
from typing import Self

import pytest

from taskmesh.api.dependencies import engine as db_engine
from taskmesh.engine import TaskMeshEngine
from taskmesh.errors import JobOwnershipError
from taskmesh.models import JobCreate, JobStatus


class _FakePipeline:
    """Minimal async pipeline used by the Redis rate limiter."""

    def __init__(self) -> None:
        self.commands: list[tuple] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def zremrangebyscore(self, *args) -> None:
        self.commands.append(("zremrangebyscore", args))

    def zcard(self, *args) -> None:
        self.commands.append(("zcard", args))

    def zadd(self, *args) -> None:
        self.commands.append(("zadd", args))

    def expire(self, *args) -> None:
        self.commands.append(("expire", args))

    async def execute(self) -> list:
        return [0, 0, 1, True]


class FakeRedis:
    """Records published events and answers rate-limit pipelines."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline()


@pytest.fixture()
def fake_redis(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr("taskmesh.engine.redis_client", client)
    return client


def _status(job: dict) -> str:
    return getattr(job["status"], "value", job["status"])


@pytest.mark.asyncio
async def test_create_job_and_fetch(fake_redis):
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
    assert _status(created) == JobStatus.PENDING.value
    # Retrieve same job
    fetched = await engine.get_job(created["id"])
    assert fetched == created
    # List jobs returns at least this one
    jobs = await engine.list_jobs(tenant_id="test")
    assert any(j["id"] == created["id"] for j in jobs)
    # Verify a log was published
    assert any(chan == "taskmesh_logs" for chan, _ in fake_redis.published)


@pytest.mark.asyncio
async def test_idempotent_job_creation(fake_redis):
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


@pytest.mark.asyncio
async def test_scheduled_job_is_not_leased(fake_redis):
    """A future ``execute_at`` keeps the job out of the pending queue."""
    from datetime import timedelta

    from taskmesh.models import utc_now

    engine = TaskMeshEngine()
    created = await engine.create_job(
        JobCreate(
            job_type="text.process",
            payload={"text": "later"},
            tenant_id="sched",
            execute_at=utc_now() + timedelta(hours=1),
        )
    )
    assert _status(created) == JobStatus.SCHEDULED.value
    assert await engine.lease_next_job("worker-1", tenant_id="sched") is None


@pytest.mark.asyncio
async def test_complete_job_refuses_a_worker_that_lost_its_lease(fake_redis):
    engine = TaskMeshEngine()
    created = await engine.create_job(
        JobCreate(job_type="text.process", payload={"text": "owned"}, tenant_id="lease")
    )
    leased = await engine.lease_next_job("worker-a", tenant_id="lease")
    assert leased is not None

    with pytest.raises(JobOwnershipError):
        await engine.complete_job(created["id"], {"words": 1}, worker_id="worker-b")

    completed = await engine.complete_job(created["id"], {"words": 1}, worker_id="worker-a")
    assert _status(completed) == JobStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_requeue_expired_leases_returns_the_job_to_pending(fake_redis):
    from datetime import timedelta

    from sqlalchemy import update

    from taskmesh.db.models import Job as OrmJob
    from taskmesh.models import utc_now

    engine = TaskMeshEngine()
    created = await engine.create_job(
        JobCreate(job_type="text.process", payload={"text": "stuck"}, tenant_id="leases")
    )
    await engine.lease_next_job("dead-worker", tenant_id="leases")

    # Pretend the lease was taken long ago.
    async with db_engine.begin() as conn:
        await conn.execute(
            update(OrmJob)
            .where(OrmJob.id == created["id"])
            .values(started_at=utc_now() - timedelta(hours=2))
        )

    requeued = await engine.requeue_expired_leases(lease_seconds=60)
    assert requeued >= 1
    job = await engine.get_job(created["id"])
    assert _status(job) == JobStatus.PENDING.value
    assert job["worker_id"] is None
