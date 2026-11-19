"""Job lifecycle, worker registry and reporting tests against the real engine."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Self

import pytest

from taskmesh.engine import TaskMeshEngine
from taskmesh.models import JobCreate, WorkerHeartbeat, utc_now


class _FakePipeline:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def zremrangebyscore(self, *args) -> None:
        pass

    def zcard(self, *args) -> None:
        pass

    def zadd(self, *args) -> None:
        pass

    def expire(self, *args) -> None:
        pass

    async def execute(self) -> list:
        return [0, 0, 1, True]


class FakeRedis:
    async def publish(self, channel: str, message: str) -> int:
        return 1

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    monkeypatch.setattr("taskmesh.engine.redis_client", FakeRedis())


def _status(job: dict) -> str:
    return getattr(job["status"], "value", job["status"])


async def _create(engine: TaskMeshEngine, **kwargs) -> dict:
    params = {
        "job_type": "text.process",
        "payload": {"text": "lifecycle"},
        "tenant_id": "lifecycle",
    }
    params.update(kwargs)
    return await engine.create_job(JobCreate(**params))


@pytest.mark.asyncio
async def test_retries_eventually_dead_letter_the_job():
    engine = TaskMeshEngine()
    job = await _create(engine, max_retries=1)
    await engine.lease_job_by_id(job["id"], "w-1")

    first = await engine.fail_job(job["id"], "boom")
    assert _status(first) == "scheduled"
    assert first["retry_count"] == 1

    await engine.lease_job_by_id(job["id"], "w-1")
    second = await engine.fail_job(job["id"], "boom again")

    assert _status(second) == "dead_letter"
    assert second["completed_at"] is not None


@pytest.mark.asyncio
async def test_replay_only_accepts_dead_letter_jobs():
    engine = TaskMeshEngine()
    job = await _create(engine, max_retries=0)
    await engine.lease_job_by_id(job["id"], "w-1")
    await engine.fail_job(job["id"], "fatal")

    replayed = await engine.replay_dead_letter(job["id"])

    assert _status(replayed) == "pending"
    assert replayed["retry_count"] == 0
    assert replayed["failure_reason"] is None

    with pytest.raises(ValueError, match="job_not_in_dead_letter"):
        await engine.replay_dead_letter(job["id"])


@pytest.mark.asyncio
async def test_cancel_only_accepts_queued_jobs():
    engine = TaskMeshEngine()
    job = await _create(engine)

    cancelled = await engine.cancel_job(job["id"])
    assert _status(cancelled) == "canceled"

    with pytest.raises(ValueError):
        await engine.cancel_job(job["id"])


@pytest.mark.asyncio
async def test_cancel_with_an_invalid_id_raises_key_error():
    with pytest.raises(KeyError):
        await TaskMeshEngine().cancel_job("not-a-uuid")


@pytest.mark.asyncio
async def test_duplicate_copies_the_original_job():
    engine = TaskMeshEngine()
    job = await _create(engine, priority=7, max_retries=2)

    copy = await engine.duplicate_job(job["id"])

    assert copy["id"] != job["id"]
    assert copy["job_type"] == job["job_type"]
    assert copy["payload"] == job["payload"]
    assert copy["priority"] == 7
    assert copy["tenant_id"] == job["tenant_id"]


@pytest.mark.asyncio
async def test_delete_removes_the_job():
    engine = TaskMeshEngine()
    job = await _create(engine)

    await engine.delete_job(job["id"])

    assert await engine.get_job(job["id"]) is None
    # Deleting an unknown or malformed id is a no-op.
    await engine.delete_job(str(uuid.uuid4()))
    await engine.delete_job("not-a-uuid")


@pytest.mark.asyncio
async def test_list_filters_and_pagination():
    engine = TaskMeshEngine()
    first = await _create(engine, tenant_id="list-a")
    second = await _create(engine, tenant_id="list-a")
    await engine.cancel_job(second["id"])

    all_a = await engine.list_jobs(tenant_id="list-a")
    cancelled = await engine.list_jobs(tenant_id="list-a", status_filter="canceled")
    limited = await engine.list_jobs(tenant_id="list-a", limit=1)

    assert {first["id"], second["id"]} <= {job["id"] for job in all_a}
    assert [job["id"] for job in cancelled] == [second["id"]]
    assert len(limited) == 1


@pytest.mark.asyncio
async def test_release_due_jobs_moves_scheduled_work_to_pending():
    engine = TaskMeshEngine()
    job = await _create(engine, execute_at=utc_now() + timedelta(hours=1))
    assert _status(job) == "scheduled"

    assert await engine.release_due_jobs() == 0  # not due yet

    from sqlalchemy import update

    from taskmesh.api.dependencies import engine as db_engine
    from taskmesh.db.models import Job as OrmJob

    async with db_engine.begin() as conn:
        await conn.execute(
            update(OrmJob)
            .where(OrmJob.id == job["id"])
            .values(execute_at=utc_now() - timedelta(minutes=1))
        )

    assert await engine.release_due_jobs() >= 1
    assert _status(await engine.get_job(job["id"])) == "pending"


@pytest.mark.asyncio
async def test_worker_registry_heartbeat_and_expiry():
    engine = TaskMeshEngine()
    heartbeat = WorkerHeartbeat(
        worker_id=f"registry-{uuid.uuid4().hex[:6]}",
        hostname="host-1",
        cpu_usage=12.5,
        memory_usage=33.0,
        active_jobs=2,
    )

    registered = await engine.heartbeat(heartbeat)
    workers = await engine.list_workers()
    active = await engine.list_workers(active_only=True)

    assert registered["id"] == heartbeat.worker_id
    assert any(worker["id"] == heartbeat.worker_id for worker in workers)
    assert any(worker["id"] == heartbeat.worker_id for worker in active)

    # A zero-minute timeout marks everything inactive.
    expired = await engine.heartbeat_expired_workers(timeout_minutes=0)
    assert expired >= 1


@pytest.mark.asyncio
async def test_events_are_filterable():
    engine = TaskMeshEngine()
    job = await _create(engine)

    events = await engine.list_events(job_id=job["id"])
    completed_only = await engine.list_events(event_type="JobCompleted")

    assert any(event["event_type"] == "JobCreated" for event in events)
    assert all(event["job_id"] == job["id"] for event in events)
    assert all(event["event_type"] == "JobCompleted" for event in completed_only)


@pytest.mark.asyncio
async def test_metrics_and_time_series_report_real_counts():
    engine = TaskMeshEngine()
    await _create(engine)

    metrics = await engine.metrics()
    series = await engine.analytics_time_series(hours=24)

    assert metrics.pending >= 1
    assert metrics.throughput_per_minute >= 0
    assert isinstance(series, list)
    for bucket in series:
        assert {"hour", "created", "completed", "failed"} <= set(bucket)


@pytest.mark.asyncio
async def test_missing_and_malformed_ids_are_handled():
    engine = TaskMeshEngine()
    missing = str(uuid.uuid4())

    assert await engine.get_job(missing) is None
    assert await engine.get_job("not-a-uuid") is None
    with pytest.raises(KeyError):
        await engine.complete_job("not-a-uuid")
    with pytest.raises(KeyError):
        await engine.fail_job(missing, "no such job")
