import pytest
from httpx import ASGITransport, AsyncClient
from taskmesh.api.main import app

@pytest.mark.asyncio
async def test_health_route():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_metrics_route_not_implemented():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/metrics/")
        assert resp.status_code == 404