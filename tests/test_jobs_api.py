"""Job API tests against the real engine: tenancy, roles and worker callbacks."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from support import ADMIN_HEADERS, WORKER_HEADERS, bearer_headers, worker_headers
from taskmesh.api.main import app
from taskmesh.engine import engine
from taskmesh.models import JobCreate, utc_now


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_job(tenant: str, text: str = "hello") -> dict:
    return await engine.create_job(
        JobCreate(job_type="text.process", payload={"text": text}, tenant_id=tenant)
    )


@pytest.mark.asyncio
async def test_developer_cannot_create_a_job_for_another_tenant():
    async with _client() as client:
        response = await client.post(
            "/jobs/",
            json={
                "job_type": "text.process",
                "payload": {"text": "hi"},
                "tenant_id": "someone-else",
            },
            headers=bearer_headers("developer", tenant="team-a"),
        )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == "team-a"


@pytest.mark.asyncio
async def test_tenant_isolation_on_read():
    mine = await _create_job("tenant-a")
    theirs = await _create_job("tenant-b")

    async with _client() as client:
        listing = await client.get("/jobs/", headers=bearer_headers("viewer", tenant="tenant-a"))
        own_job = await client.get(f"/jobs/{mine['id']}", headers=bearer_headers("viewer", "tenant-a"))
        foreign_job = await client.get(
            f"/jobs/{theirs['id']}", headers=bearer_headers("viewer", "tenant-a")
        )
        admin_foreign = await client.get(f"/jobs/{theirs['id']}", headers=ADMIN_HEADERS)

    assert listing.status_code == 200
    assert {job["id"] for job in listing.json()} <= {mine["id"]}
    assert own_job.status_code == 200
    # A job in another tenant is indistinguishable from a missing one.
    assert foreign_job.status_code == 404
    assert admin_foreign.status_code == 200


@pytest.mark.asyncio
async def test_tenant_isolation_on_mutation():
    theirs = await _create_job("tenant-b")

    async with _client() as client:
        response = await client.post(
            f"/jobs/{theirs['id']}/cancel",
            headers=bearer_headers("developer", tenant="tenant-a"),
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_worker_lease_complete_fail_flow():
    job = await _create_job("worker-flow")

    async with _client() as client:
        lease = await client.post(f"/jobs/{job['id']}/lease", headers=worker_headers("w-1"))
        assert lease.status_code == 200
        assert lease.json()["status"] == "running"

        # A different worker cannot complete a lease it does not hold.
        stolen = await client.post(
            f"/jobs/{job['id']}/complete", headers=worker_headers("w-2")
        )
        assert stolen.status_code == 409

        fail = await client.post(
            f"/jobs/{job['id']}/fail",
            params={"reason": "boom"},
            headers=worker_headers("w-1"),
        )
        assert fail.status_code == 200
        assert fail.json()["retry_count"] == 1
        assert fail.json()["status"] == "scheduled"


@pytest.mark.asyncio
async def test_worker_callbacks_report_unknown_jobs():
    missing = str(uuid.uuid4())

    async with _client() as client:
        complete = await client.post(f"/jobs/{missing}/complete", headers=WORKER_HEADERS)
        fail = await client.post(f"/jobs/{missing}/fail", headers=WORKER_HEADERS)

    assert complete.status_code == 404
    assert fail.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_replay_a_dead_letter_job():
    job = await _create_job("dlq")
    await engine.lease_job_by_id(job["id"], "w-1")
    for _ in range(6):
        await engine.fail_job(job["id"], "always fails")

    async with _client() as client:
        forbidden = await client.post(
            f"/jobs/{job['id']}/replay", headers=bearer_headers("developer")
        )
        replay = await client.post(f"/jobs/{job['id']}/replay", headers=ADMIN_HEADERS)

    assert forbidden.status_code == 403
    assert replay.status_code == 200
    assert replay.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_admin_can_delete_and_only_admin_can():
    job = await _create_job("delete-me")

    async with _client() as client:
        forbidden = await client.delete(
            f"/jobs/{job['id']}", headers=bearer_headers("developer")
        )
        deleted = await client.delete(f"/jobs/{job['id']}", headers=ADMIN_HEADERS)

    assert forbidden.status_code == 403
    assert deleted.status_code == 204
    assert await engine.get_job(job["id"]) is None


@pytest.mark.asyncio
async def test_scheduled_job_stays_out_of_the_queue_until_due():
    job = await engine.create_job(
        JobCreate(
            job_type="text.process",
            payload={"text": "later"},
            tenant_id="scheduling",
            execute_at=utc_now() + timedelta(hours=1),
        )
    )

    async with _client() as client:
        status = await client.get(f"/jobs/{job['id']}", headers=ADMIN_HEADERS)

    assert status.json()["status"] == "scheduled"
