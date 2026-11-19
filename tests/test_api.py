"""System endpoints: health, readiness, CORS, security headers and limits."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from taskmesh.api.main import app
from taskmesh.config import get_settings


def _client(**kwargs) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", **kwargs)


@pytest.mark.asyncio
async def test_health_is_a_plain_liveness_check():
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_reports_database_and_redis():
    async with _client() as client:
        response = await client.get("/ready")

    body = response.json()
    assert body["checks"]["database"] is True
    # Redis is optional outside production.
    assert "redis" in body["checks"]
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_readiness_fails_when_the_database_is_unreachable(monkeypatch):
    async def _down() -> bool:
        return False

    monkeypatch.setattr("taskmesh.api.main.database_ready", _down)

    async with _client() as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] is False


@pytest.mark.asyncio
async def test_security_headers_and_request_id_are_present():
    async with _client() as client:
        response = await client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_a_supplied_request_id_is_echoed():
    async with _client() as client:
        response = await client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["X-Request-ID"] == "abc-123"


@pytest.mark.asyncio
async def test_cors_allows_only_configured_origins():
    settings = get_settings()
    allowed = settings.cors_origins[0]

    async with _client() as client:
        permitted = await client.options(
            "/text/jobs",
            headers={
                "Origin": allowed,
                "Access-Control-Request-Method": "POST",
            },
        )
        rejected = await client.options(
            "/text/jobs",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert permitted.headers.get("access-control-allow-origin") == allowed
    assert permitted.headers.get("access-control-allow-credentials") is None
    assert "access-control-allow-origin" not in rejected.headers


@pytest.mark.asyncio
async def test_oversized_bodies_are_rejected_with_413():
    limit = get_settings().max_request_bytes

    async with _client() as client:
        response = await client.post(
            "/text/jobs",
            content=b"x" * (limit + 1),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_openapi_and_docs_are_served():
    async with _client() as client:
        schema = await client.get("/openapi.json")
        docs = await client.get("/docs")

    assert schema.status_code == 200
    assert docs.status_code == 200
    schemes = schema.json()["components"]["securitySchemes"]
    assert "BearerAuth" in schemes
    assert "WorkerToken" in schemes
