"""Rate limiter behaviour: windows, configuration and bounded memory."""

from __future__ import annotations

from typing import ClassVar

import pytest
from fastapi import HTTPException

from taskmesh.api.rate_limit import SlidingWindowLimiter, client_key
from taskmesh.config import get_settings


class _Clock:
    """Controllable replacement for ``time.monotonic``."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr("taskmesh.api.rate_limit.time.monotonic", fake)
    return fake


def test_allows_calls_up_to_the_limit(clock):
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60)

    for _ in range(3):
        limiter.check("client", "slow down")

    with pytest.raises(HTTPException) as excinfo:
        limiter.check("client", "slow down")
    assert excinfo.value.status_code == 429


def test_window_slides_so_old_calls_expire(clock):
    limiter = SlidingWindowLimiter(limit=2, window_seconds=10)

    limiter.check("client", "slow down")
    limiter.check("client", "slow down")
    with pytest.raises(HTTPException):
        limiter.check("client", "slow down")

    clock.advance(11)

    limiter.check("client", "slow down")  # allowed again


def test_clients_are_isolated(clock):
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)

    limiter.check("client-a", "slow down")

    limiter.check("client-b", "slow down")  # a different client is unaffected


def test_tracked_clients_stay_bounded(clock):
    limiter = SlidingWindowLimiter(limit=5, window_seconds=10, max_tracked_clients=5)

    for index in range(50):
        limiter.check(f"client-{index}", "slow down")
        clock.advance(0.1)

    assert len(limiter._windows) <= 5


def test_client_key_prefers_the_forwarded_address(monkeypatch):
    class Request:
        headers: ClassVar[dict[str, str]] = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
        client = None

    class DirectRequest:
        headers: ClassVar[dict[str, str]] = {}
        client = type("Client", (), {"host": "198.51.100.4"})()

    assert client_key(Request()) == "203.0.113.7"
    assert client_key(DirectRequest()) == "198.51.100.4"


def test_limits_come_from_configuration():
    settings = get_settings()

    assert settings.rate_limit_submissions >= 1
    assert settings.rate_limit_window_seconds >= 1
