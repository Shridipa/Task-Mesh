"""In-memory sliding-window rate limiter for the public demo endpoints.

Each endpoint owns its own limiter instance, so a busy text demo cannot lock a
visitor out of the analysis demo (and vice versa). The limiter is deliberately
process-local: it protects the public surface of a single deployment without
requiring Redis.
"""

from __future__ import annotations

import time
from collections import deque

from fastapi import HTTPException, Request, status

MAX_TRACKED_CLIENTS = 1024


def client_key(request: Request) -> str:
    """Identify the caller, honouring a proxy's ``X-Forwarded-For`` header."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class SlidingWindowLimiter:
    """Allow at most ``limit`` calls per client in a rolling window."""

    def __init__(
        self,
        limit: int = 10,
        window_seconds: float = 60.0,
        max_tracked_clients: int = MAX_TRACKED_CLIENTS,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_tracked_clients = max_tracked_clients
        self._windows: dict[str, deque[float]] = {}

    def check(self, key: str, message: str) -> None:
        """Record a call for ``key`` or raise HTTP 429 when the window is full."""
        now = time.monotonic()

        if len(self._windows) > self.max_tracked_clients:
            for stale in [client for client, window in self._windows.items() if not window]:
                del self._windows[stale]

        window = self._windows.setdefault(key, deque())
        while window and now - window[0] > self.window_seconds:
            window.popleft()
        if len(window) >= self.limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
        window.append(now)
