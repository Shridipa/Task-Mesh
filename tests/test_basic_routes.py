import pytest
from httpx import AsyncClient
from src.taskmesh.api.main import app

@pytest.mark.asyncio
async def test_health_route():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_metrics_route_not_implemented():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/metrics")
        # Assuming metrics endpoint returns empty dict or 200
        assert resp.status_code == 200
