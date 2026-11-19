"""Helpers shared by the test suite (auth headers, tokens, worker secrets)."""

from __future__ import annotations

import os

from taskmesh.api.auth import create_access_token

ADMIN_API_KEY = "test-admin-key"
DEVELOPER_API_KEY = "test-developer-key"
VIEWER_API_KEY = "test-viewer-key"

WORKER_SECRET = os.getenv("WORKER_SECRET", "taskmesh_secret")


def bearer_headers(
    role: str = "admin", tenant: str = "default", subject: str | None = None
) -> dict[str, str]:
    """Build an ``Authorization`` header carrying a token for ``role``."""
    token, _ = create_access_token(subject or f"test-{role}", role, tenant)
    return {"Authorization": f"Bearer {token}"}


def worker_headers(worker_id: str = "test-worker") -> dict[str, str]:
    """Build the headers a worker uses for lease/complete/fail callbacks."""
    return {"X-Worker-Token": WORKER_SECRET, "X-Worker-Id": worker_id}


ADMIN_HEADERS = bearer_headers("admin")
DEVELOPER_HEADERS = bearer_headers("developer")
VIEWER_HEADERS = bearer_headers("viewer")
WORKER_HEADERS = worker_headers()

SAMPLE_JOB = {"job_type": "email", "payload": {"to": "user@example.com"}, "priority": 5}
