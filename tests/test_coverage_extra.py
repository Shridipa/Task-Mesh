import pytest
from httpx import ASGITransport, AsyncClient

from taskmesh.api.main import app
from taskmesh.api.auth import (
    require_write,
    require_read,
    require_admin,
    require_worker,
    require_worker_token,
)
from taskmesh.engine import engine as real_engine


# Mock engine functions
class MockEngine:
    async def create_job(self, job):
        return {"id": "1234", "status": "pending"}

    async def list_jobs(self, **kwargs):
        return [{"id": "1234", "status": "pending"}]

    async def get_job(self, job_id):
        if job_id == "1234":
            return {"id": "1234", "status": "pending"}
        return None

    async def lease_job_by_id(self, job_id):
        if job_id == "1234":
            return {"id": "1234", "status": "leased"}
        return None

    async def complete_job(self, job_id):
        return None

    async def fail_job(self, job_id, reason):
        return {"id": job_id, "failed": True, "reason": reason}

    async def replay_dead_letter(self, job_id):
        return {"id": job_id, "status": "pending"}

    async def duplicate_job(self, job_id):
        return {"id": "dup", "original": job_id}

    async def cancel_job(self, job_id):
        return {"id": job_id, "cancelled": True}

    async def delete_job(self, job_id):
        return None


mock_engine = MockEngine()


@pytest.fixture(autouse=True)
def patch_engine(monkeypatch):
    """Patch the engine singleton's methods in-place, since routes call
    `engine.create_job(...)` directly rather than via Depends()."""
    for name in (
        "create_job",
        "list_jobs",
        "get_job",
        "lease_job_by_id",
        "complete_job",
        "fail_job",
        "replay_dead_letter",
        "duplicate_job",
        "cancel_job",
        "delete_job",
    ):
        monkeypatch.setattr(real_engine, name, getattr(mock_engine, name))


# Bypass auth for these tests — override every auth dependency used by the routes
app.dependency_overrides[require_write] = lambda: "test-user"
app.dependency_overrides[require_read] = lambda: "test-user"
app.dependency_overrides[require_admin] = lambda: "test-user"
app.dependency_overrides[require_worker] = lambda: "test-worker"
app.dependency_overrides[require_worker_token] = lambda: "test-token"


@pytest.mark.asyncio
async def test_create_and_get_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/jobs/", json={"job_type": "test", "payload": {}, "priority": 1})
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "1234"
        resp = await ac.get(f"/jobs/{data['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_get_missing_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/jobs/not-found")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lease_and_complete_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/jobs/1234/lease")
        assert resp.status_code == 200
        assert resp.json()["status"] == "leased"
        resp = await ac.post("/jobs/1234/complete")
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_fail_and_replay_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/jobs/1234/fail", params={"reason": "error"})
        assert resp.status_code == 200
        assert resp.json()["failed"] is True
        resp = await ac.post("/jobs/1234/replay")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"