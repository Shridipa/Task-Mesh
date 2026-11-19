"""Authentication and authorization tests.

These exercise the real token endpoint and the real dependencies; nothing is
stubbed, so a failure here means authorization is genuinely broken.
"""

from __future__ import annotations

import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from support import (
    ADMIN_API_KEY,
    ADMIN_HEADERS,
    VIEWER_API_KEY,
    VIEWER_HEADERS,
    WORKER_HEADERS,
    bearer_headers,
    worker_headers,
)
from taskmesh.api.auth import ALGORITHM, InvalidToken, decode_access_token
from taskmesh.api.main import app
from taskmesh.config import get_settings


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _token_for(role: str, *, ttl: int = 60, issuer: str | None = None) -> str:
    settings = get_settings()
    now = int(time.time())
    claims = {
        "sub": "test-subject",
        "role": role,
        "tenant": "default",
        "iat": now,
        "exp": now + ttl,
        "iss": issuer or settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_api_key_is_exchanged_for_a_signed_token():
    async with _client() as client:
        response = await client.post("/auth/token", json={"api_key": ADMIN_API_KEY})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert body["tenant"] == "default"
    assert body["expires_at"] > time.time()
    assert ADMIN_API_KEY not in body["subject"]

    principal = decode_access_token(body["access_token"])
    assert principal.role == "admin"
    assert principal.subject == body["subject"]


@pytest.mark.asyncio
async def test_invalid_api_key_is_rejected():
    async with _client() as client:
        response = await client.post("/auth/token", json={"api_key": "not-a-real-key"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_key_yields_a_viewer_token():
    async with _client() as client:
        response = await client.post("/auth/token", json={"api_key": VIEWER_API_KEY})

    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


@pytest.mark.asyncio
async def test_whoami_requires_and_returns_identity():
    async with _client() as client:
        unauthenticated = await client.get("/auth/me")
        authenticated = await client.get("/auth/me", headers=ADMIN_HEADERS)

    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    assert authenticated.status_code == 200
    assert authenticated.json()["role"] == "admin"


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_a_client_supplied_role_header_is_ignored():
    """The removed X-Role contract must not grant access any more."""
    async with _client() as client:
        response = await client.get("/jobs/", headers={"X-Role": "admin"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tampered_signature_is_rejected():
    token = _token_for("admin")
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")

    async with _client() as client:
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_is_rejected():
    async with _client() as client:
        response = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {_token_for('admin', ttl=-5)}"}
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_issuer_and_audience_are_rejected():
    async with _client() as client:
        wrong_issuer = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {_token_for('admin', issuer='someone-else')}"},
        )

    assert wrong_issuer.status_code == 401

    settings = get_settings()
    now = int(time.time())
    wrong_audience = jwt.encode(
        {
            "sub": "x",
            "role": "admin",
            "tenant": "default",
            "iat": now,
            "exp": now + 60,
            "iss": settings.jwt_issuer,
            "aud": "another-api",
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    with pytest.raises(InvalidToken):
        decode_access_token(wrong_audience)


@pytest.mark.asyncio
async def test_unsigned_and_unknown_role_tokens_are_rejected():
    settings = get_settings()
    unsigned = jwt.encode({"sub": "x", "role": "admin"}, "secret", algorithm="HS256")
    with pytest.raises(InvalidToken):
        decode_access_token(unsigned)

    unknown_role = jwt.encode(
        {
            "sub": "x",
            "role": "superuser",
            "tenant": "default",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    with pytest.raises(InvalidToken):
        decode_access_token(unknown_role)


@pytest.mark.asyncio
async def test_alg_none_tokens_are_rejected():
    settings = get_settings()
    forged = jwt.encode(
        {
            "sub": "attacker",
            "role": "admin",
            "tenant": "default",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        key="",
        algorithm="none",
    )

    async with _client() as client:
        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
SAMPLE_JOB = {"job_type": "text.process", "payload": {"text": "hello"}}


@pytest.mark.asyncio
async def test_role_based_access_is_enforced():
    async with _client() as client:
        viewer_write = await client.post("/jobs/", json=SAMPLE_JOB, headers=VIEWER_HEADERS)
        viewer_read = await client.get("/jobs/", headers=VIEWER_HEADERS)
        developer_write = await client.post("/jobs/", json=SAMPLE_JOB, headers=bearer_headers("developer"))
        developer_admin_route = await client.get("/scheduler/status", headers=bearer_headers("developer"))
        admin_route = await client.get("/scheduler/status", headers=ADMIN_HEADERS)

    assert viewer_write.status_code == 403
    assert viewer_read.status_code == 200
    assert developer_write.status_code == 201
    assert developer_admin_route.status_code == 403
    assert admin_route.status_code == 200


@pytest.mark.asyncio
async def test_worker_token_endpoints_require_the_shared_secret():
    async with _client() as client:
        missing = await client.post("/jobs/does-not-exist/lease")
        wrong = await client.post(
            "/jobs/does-not-exist/lease", headers={"X-Worker-Token": "wrong-secret"}
        )
        valid = await client.post("/jobs/does-not-exist/lease", headers=WORKER_HEADERS)

    assert missing.status_code == 401
    assert wrong.status_code == 403
    # Authentication passed, so the route reports the job as unavailable.
    assert valid.status_code == 404


@pytest.mark.asyncio
async def test_worker_cannot_heartbeat_without_the_secret():
    payload = {
        "worker_id": "w1",
        "hostname": "host",
        "cpu_usage": 10,
        "memory_usage": 20,
        "active_jobs": 0,
    }
    async with _client() as client:
        response = await client.post("/workers/heartbeat", json=payload)
        accepted = await client.post("/workers/heartbeat", json=payload, headers=worker_headers("w1"))

    assert response.status_code == 401
    assert accepted.status_code == 200


@pytest.mark.asyncio
async def test_token_endpoint_is_rate_limited():
    async with _client() as client:
        statuses = [
            (await client.post("/auth/token", json={"api_key": "wrong-key-value"})).status_code
            for _ in range(12)
        ]

    assert 429 in statuses
