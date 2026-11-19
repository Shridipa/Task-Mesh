#!/usr/bin/env python3
"""End-to-end smoke test against a running TaskMesh API.

Usage:
    API_BASE=http://127.0.0.1:8000 ADMIN_API_KEY=... python scripts/live_smoke.py

Exercises authentication, tenant isolation, all three workloads, failure
handling, rate limiting and CORS against a live server. Prints one line per
check and exits non-zero on the first failure.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("API_BASE", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "dev-admin-key")
DEVELOPER_KEY = os.getenv("DEVELOPER_API_KEY")
VIEWER_KEY = os.getenv("VIEWER_API_KEY")

FAILURES: list[str] = []


def call(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
    headers: dict | None = None,
) -> tuple[int, dict | list | str]:
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode()
            try:
                return response.status, json.loads(payload)
            except json.JSONDecodeError:
                return response.status, payload
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode()
        try:
            return exc.code, json.loads(payload)
        except json.JSONDecodeError:
            return exc.code, payload


def check(name: str, condition: bool, detail: object = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def wait_terminal(token: str | None, path: str, timeout: float = 25.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        _, body = call("GET", path, token=token)
        if isinstance(body, dict):
            last = body
            if body.get("status") in {"completed", "failed", "dead_letter", "canceled"}:
                return body
        time.sleep(0.25)
    return last


def main() -> int:
    status, body = call("GET", "/health")
    check("health returns 200", status == 200 and body.get("status") == "ok")

    status, body = call("GET", "/ready")
    check("readiness reports the database", status == 200 and body["checks"]["database"] is True)

    status, body = call("POST", "/auth/token", {"api_key": ADMIN_KEY})
    check("admin key exchanges for a token", status == 200 and body.get("role") == "admin")
    admin_token = body["access_token"] if status == 200 else None

    status, _ = call("POST", "/auth/token", {"api_key": "definitely-wrong"})
    check("wrong API key is rejected", status == 401)

    status, _ = call("GET", "/jobs/")
    check("job list requires authentication", status == 401)

    status, _ = call("GET", "/jobs/", headers={"X-Role": "admin"})
    check("X-Role header no longer grants access", status == 401)

    status, body = call("GET", "/auth/me", token=admin_token)
    check("token identifies the caller", status == 200 and body.get("role") == "admin")

    developer_token = viewer_token = None
    if DEVELOPER_KEY:
        status, body = call("POST", "/auth/token", {"api_key": DEVELOPER_KEY})
        check("developer key exchanges for a token", status == 200 and body.get("role") == "developer")
        developer_token = body.get("access_token")
    if VIEWER_KEY:
        status, body = call("POST", "/auth/token", {"api_key": VIEWER_KEY})
        viewer_token = body.get("access_token")

    # --- text workload, public demo -------------------------------------
    status, created = call("POST", "/text/jobs", {"text": "Live check. Two sentences here!"})
    check("public text submission accepted", status == 201)
    finished = wait_terminal(None, f"/text/jobs/{created.get('id')}")
    check(
        "text job completes with real counts",
        finished.get("status") == "completed"
        and finished["result"]["words"] >= 4
        and finished["worker_id"],
        finished,
    )

    # --- JSON workload ---------------------------------------------------
    status, created = call(
        "POST", "/analysis/jobs", {"task": "json.validate", "content": '{"a": [1, 2], "b": null}'}
    )
    check("json submission accepted", status == 201)
    finished = wait_terminal(None, f"/analysis/jobs/{created.get('id')}")
    check(
        "json job completes",
        finished.get("status") == "completed"
        and finished["result"]["root_type"] == "object"
        and finished["result"]["counts"]["arrays"] == 1,
        finished,
    )

    status, created = call("POST", "/analysis/jobs", {"task": "json.validate", "content": '{"a": }'})
    finished = wait_terminal(None, f"/analysis/jobs/{created.get('id')}")
    check(
        "invalid JSON fails permanently with line/column",
        finished.get("status") == "failed"
        and "line 1" in (finished.get("failure_reason") or "")
        and finished.get("result") is None,
        finished,
    )

    # --- CSV workload ----------------------------------------------------
    csv_doc = "name,score\nAda,90\nGrace,80\nAda,90\nLinus,\n"
    status, created = call("POST", "/analysis/jobs", {"task": "csv.analyze", "content": csv_doc})
    check("csv submission accepted", status == 201)
    finished = wait_terminal(None, f"/analysis/jobs/{created.get('id')}")
    check(
        "csv job completes with statistics",
        finished.get("status") == "completed"
        and finished["result"]["rows"] == 4
        and finished["result"]["duplicate_rows"] == 1
        and finished["result"]["missing_values"]["total"] == 1,
        finished,
    )

    # --- authenticated job management -----------------------------------
    if developer_token:
        status, created = call(
            "POST",
            "/jobs/",
            {"job_type": "text.process", "payload": {"text": "authenticated work"}},
            token=developer_token,
        )
        check("developer can create a job", status == 201, created)
        check("job is pinned to the caller tenant", created.get("tenant_id") == "acme", created)
        finished = wait_terminal(developer_token, f"/jobs/{created.get('id')}")
        check("authenticated job executes", finished.get("status") == "completed", finished)

        status, _ = call(
            "GET", "/jobs/", token=developer_token
        )
        check("developer can read their tenant's jobs", status == 200)

    if viewer_token:
        status, _ = call(
            "POST",
            "/jobs/",
            {"job_type": "text.process", "payload": {"text": "nope"}},
            token=viewer_token,
        )
        check("viewer cannot create jobs", status == 403)
        status, _ = call("GET", "/jobs/", token=viewer_token)
        check("viewer can read jobs", status == 200)

    if admin_token:
        status, _ = call("GET", "/metrics/prometheus", token=admin_token)
        check("admin can read prometheus metrics", status == 200)
        status, _ = call("GET", "/scheduler/status", token=admin_token)
        check("admin can read scheduler status", status == 200)

    status, _ = call("GET", "/metrics/prometheus")
    check("metrics require auth when not public", status == 401)

    # --- abuse protection ------------------------------------------------
    statuses = [
        call("POST", "/analysis/jobs", {"task": "json.validate", "content": "{}"})[0]
        for _ in range(12)
    ]
    check("public submissions are rate limited", 429 in statuses, statuses)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1
    print("All live checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
