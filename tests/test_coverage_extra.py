import pytest
from httpx import AsyncClient

from src.taskmesh.api.main import app

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

# Override the engine dependency used in routes
app.dependency_overrides["src.taskmesh.engine.engine"] = lambda: mock_engine

@pytest.mark.asyncio
async def test_create_and_get_job():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # create job
        resp = await ac.post("/jobs/", json={"job_type": "test", "payload": {}, "priority": 1})
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "1234"
        # get job
        resp = await ac.get(f"/jobs/{data['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

@pytest.mark.asyncio
async def test_get_missing_job():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/jobs/not-found")
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_lease_and_complete_job():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # lease job
        resp = await ac.post("/jobs/1234/lease")
        assert resp.status_code == 200
        assert resp.json()["status"] == "leased"
        # complete job
        resp = await ac.post("/jobs/1234/complete")
        assert resp.status_code == 204

@pytest.mark.asyncio
async def test_fail_and_replay_job():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/jobs/1234/fail", params={"reason": "error"})
        assert resp.status_code == 200
        assert resp.json()["failed"] is True
        resp = await ac.post("/jobs/1234/replay")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
