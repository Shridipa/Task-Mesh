import pytest
from fastapi import HTTPException
from taskmesh.api.auth import require_role, require_worker_token

require_admin = require_role({"admin"})


@pytest.mark.asyncio
async def test_require_role_missing_header():
    class FakeRequest:
        headers = {}

    with pytest.raises(HTTPException) as exc:
        await require_admin(FakeRequest())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_role_unknown_role():
    class FakeRequest:
        headers = {"x-role": "bogus"}

    with pytest.raises(HTTPException) as exc:
        await require_admin(FakeRequest())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_insufficient_permissions():
    class FakeRequest:
        headers = {"x-role": "viewer"}

    with pytest.raises(HTTPException) as exc:
        await require_admin(FakeRequest())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_success():
    class FakeRequest:
        headers = {"x-role": "admin"}

    result = await require_admin(FakeRequest())
    assert result == "admin"


@pytest.mark.asyncio
async def test_require_worker_token_missing():
    check = require_worker_token("secret123")

    class FakeRequest:
        headers = {}

    with pytest.raises(HTTPException) as exc:
        await check(FakeRequest())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_worker_token_invalid():
    check = require_worker_token("secret123")

    class FakeRequest:
        headers = {"x-worker-token": "wrong"}

    with pytest.raises(HTTPException) as exc:
        await check(FakeRequest())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_worker_token_valid():
    check = require_worker_token("secret123")

    class FakeRequest:
        headers = {"x-worker-token": "secret123"}

    result = await check(FakeRequest())
    assert result == "secret123"