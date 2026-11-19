"""Worker loop tests: execution, retries, permanent failures and shutdown."""

from __future__ import annotations

import asyncio

import pytest

from taskmesh.engine import TaskMeshEngine
from taskmesh.errors import JobOwnershipError
from taskmesh.models import JobCreate
from taskmesh.worker import run_worker


def _status(job: dict) -> str:
    return getattr(job["status"], "value", job["status"])


async def _queue(job_type: str = "text.process", payload: dict | None = None, **kwargs) -> dict:
    return await TaskMeshEngine().create_job(
        JobCreate(
            job_type=job_type,
            payload=payload if payload is not None else {"text": "worker test"},
            tenant_id=kwargs.pop("tenant_id", "worker-tests"),
            **kwargs,
        )
    )


@pytest.mark.asyncio
async def test_worker_executes_a_job_and_stores_the_result(clean_queue):
    job = await _queue()

    handled = await run_worker(max_jobs=1)

    assert handled == 1
    stored = await TaskMeshEngine().get_job(job["id"])
    assert _status(stored) == "completed"
    assert stored["result"]["words"] == 2
    assert stored["worker_id"]
    assert stored["started_at"] is not None
    assert stored["completed_at"] is not None


@pytest.mark.asyncio
async def test_worker_fails_invalid_input_permanently(clean_queue):
    job = await _queue(job_type="json.validate", payload={"content": '{"a": }'})

    await run_worker(max_jobs=1)

    stored = await TaskMeshEngine().get_job(job["id"])
    assert _status(stored) == "failed"
    assert stored["retry_count"] == 1
    assert "Invalid JSON" in stored["failure_reason"]
    assert stored["result"] is None


@pytest.mark.asyncio
async def test_worker_retries_a_transient_failure(clean_queue, monkeypatch):
    def explode(job_type: str, payload: dict) -> dict:
        raise RuntimeError("temporary outage")

    monkeypatch.setattr("taskmesh.worker.execute_job", explode)
    job = await _queue()

    await run_worker(max_jobs=1)

    stored = await TaskMeshEngine().get_job(job["id"])
    assert _status(stored) == "scheduled"
    assert stored["retry_count"] == 1
    assert stored["failure_reason"] == "temporary outage"
    assert stored["execute_at"] is not None


@pytest.mark.asyncio
async def test_unknown_job_types_fail_permanently(clean_queue):
    job = await _queue(job_type="image.resize", payload={})

    await run_worker(max_jobs=1)

    stored = await TaskMeshEngine().get_job(job["id"])
    assert _status(stored) == "failed"
    assert "no handler" in stored["failure_reason"]


@pytest.mark.asyncio
async def test_worker_survives_losing_its_lease(clean_queue, monkeypatch):
    """A worker whose lease was requeued must not overwrite the job."""
    job = await _queue()
    attempts: list[str] = []

    async def reject(self, job_id, result=None, worker_id=None):
        attempts.append(job_id)
        raise JobOwnershipError(f"worker {worker_id} no longer owns {job_id}")

    monkeypatch.setattr(TaskMeshEngine, "complete_job", reject)
    stop_event = asyncio.Event()
    asyncio.get_running_loop().call_later(1.5, stop_event.set)

    handled = await asyncio.wait_for(run_worker(stop_event), timeout=10)

    assert handled == 0
    assert attempts == [job["id"]]
    stored = await TaskMeshEngine().get_job(job["id"])
    assert _status(stored) == "running"


@pytest.mark.asyncio
async def test_worker_registers_a_heartbeat(clean_queue):
    await run_worker(max_jobs=0)

    workers = await TaskMeshEngine().list_workers()
    assert workers, "the worker should register itself"


@pytest.mark.asyncio
async def test_worker_stops_when_asked(clean_queue):
    stop_event = asyncio.Event()
    stop_event.set()

    handled = await asyncio.wait_for(run_worker(stop_event), timeout=5)

    assert handled == 0
