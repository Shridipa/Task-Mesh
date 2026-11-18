"""Tests for the text-processing demo: pure logic, API and real worker execution."""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from taskmesh.api.dependencies import create_schema
from taskmesh.engine import engine
from taskmesh.main import app
from taskmesh.models import JobCreate
from taskmesh.tasks import UnsupportedJobType, execute_job
from taskmesh.text_processing import (
    MAX_TEXT_LENGTH,
    clean_text,
    count_sentences,
    process_text,
)

DEV_HEADERS = {"X-Role": "developer"}

SAMPLE = "Hello world. This is TaskMesh!\n\nWorkers run tasks?"


@pytest.fixture(scope="module", autouse=True)
def _schema():
    """Create the tables once for the engine-level tests in this module."""
    asyncio.run(create_schema())


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _status(job: dict) -> str:
    """Engine dicts may hold JobStatus members; compare by value."""
    return getattr(job["status"], "value", job["status"])


def _wait_for_terminal_status(client: TestClient, job_id: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/text/jobs/{job_id}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in {"completed", "failed", "dead_letter", "canceled"}:
            return last
        time.sleep(0.2)
    raise AssertionError(f"job {job_id} never reached a terminal status: {last}")


# ---------------------------------------------------------------------------
# Text processing rules
# ---------------------------------------------------------------------------
def test_process_text_returns_expected_counts():
    result = process_text(SAMPLE)

    assert result["words"] == 8
    assert result["sentences"] == 3
    assert result["lines"] == 3
    assert result["characters"] == len(result["cleaned_text"])
    assert result["cleaned_text"] == SAMPLE


def test_process_text_normalizes_whitespace():
    result = process_text("  spaced   out \t text  \n\n\n\nsecond  line  ")

    assert result["cleaned_text"] == "spaced out text\n\nsecond line"
    assert result["words"] == 5
    assert result["lines"] == 3


def test_process_text_handles_windows_and_mac_newlines():
    assert clean_text("a\r\nb\rc") == "a\nb\nc"


def test_process_text_counts_unicode_characters():
    result = process_text("héllo wörld. 日本語のテキスト!")

    assert result["words"] == 3
    assert result["sentences"] == 2
    assert result["characters"] == len(result["cleaned_text"])


def test_count_sentences_without_terminator_counts_once():
    assert count_sentences("just one sentence") == 1
    assert count_sentences("") == 0
    assert count_sentences("Really?! Yes... Done.") == 3


def test_process_text_rejects_empty_input():
    with pytest.raises(ValueError):
        process_text("")
    with pytest.raises(ValueError):
        process_text("   \n\t  ")


def test_process_text_rejects_over_limit_input():
    with pytest.raises(ValueError):
        process_text("a" * (MAX_TEXT_LENGTH + 1))


def test_execute_job_runs_the_text_handler():
    result = execute_job("text.process", {"text": SAMPLE})

    assert result["words"] == 8
    assert result["cleaned_text"] == SAMPLE


def test_execute_job_rejects_unknown_types_and_bad_payloads():
    with pytest.raises(UnsupportedJobType):
        execute_job("email", {"to": "user@example.com"})
    with pytest.raises(ValueError):
        execute_job("text.process", {})


# ---------------------------------------------------------------------------
# Engine persistence (no worker involved, so these are deterministic)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_completed_job_result_is_persisted():
    job = await engine.create_job(
        JobCreate(job_type="text.process", payload={"text": "one two"}, tenant_id="tests")
    )
    leased = await engine.lease_job_by_id(job["id"], "test-worker")
    assert leased is not None

    await engine.complete_job(job["id"], {"words": 2})
    stored = await engine.get_job(job["id"])

    assert stored is not None
    assert _status(stored) == "completed"
    assert stored["result"] == {"words": 2}


@pytest.mark.asyncio
async def test_failed_job_uses_existing_retry_mechanism():
    job = await engine.create_job(
        JobCreate(job_type="text.process", payload={"text": "x"}, tenant_id="tests")
    )
    leased = await engine.lease_job_by_id(job["id"], "test-worker")
    assert leased is not None

    failed = await engine.fail_job(job["id"], "boom")

    assert failed["retry_count"] == 1
    assert _status(failed) == "scheduled"
    assert failed["failure_reason"] == "boom"
    assert failed["result"] is None


# ---------------------------------------------------------------------------
# HTTP API and end-to-end execution
# ---------------------------------------------------------------------------
def test_submit_text_job_creates_a_real_pending_job(client: TestClient):
    response = client.post("/text/jobs", json={"text": SAMPLE})

    assert response.status_code == 201
    job = response.json()
    assert job["job_type"] == "text.process"
    assert job["status"] in {"pending", "scheduled"}
    assert job["result"] is None
    assert job["payload"]["text"] == SAMPLE
    assert job["result"] is None


def test_submit_text_job_rejects_invalid_payloads(client: TestClient):
    assert client.post("/text/jobs", json={"text": ""}).status_code == 422
    assert client.post("/text/jobs", json={"text": "   \n  "}).status_code == 422
    assert client.post("/text/jobs", json={"text": "a" * (MAX_TEXT_LENGTH + 1)}).status_code == 422
    assert client.post("/text/jobs", json={}).status_code == 422


def test_worker_executes_the_submitted_job(client: TestClient):
    created = client.post("/text/jobs", json={"text": SAMPLE}).json()

    job = _wait_for_terminal_status(client, created["id"])

    assert job["status"] == "completed"
    assert job["worker_id"]
    assert job["started_at"] is not None
    assert job["completed_at"] is not None
    assert job["result"]["words"] == 8
    assert job["result"]["sentences"] == 3
    assert job["result"]["lines"] == 3
    assert job["result"]["characters"] == len(SAMPLE)
    assert job["result"]["cleaned_text"] == SAMPLE


def test_completed_result_survives_a_page_reload(client: TestClient):
    created = client.post("/text/jobs", json={"text": "Persist me. Please!"}).json()
    _wait_for_terminal_status(client, created["id"])

    refreshed = client.get(f"/text/jobs/{created['id']}")

    assert refreshed.status_code == 200
    assert refreshed.json()["result"]["sentences"] == 2
    assert refreshed.json()["result"]["cleaned_text"] == "Persist me. Please!"


def test_public_lookup_hides_unknown_and_non_text_jobs(client: TestClient):
    assert client.get(f"/text/jobs/{uuid.uuid4()}").status_code == 404

    other = client.post(
        "/jobs/",
        json={"job_type": "email", "payload": {"to": "user@example.com"}},
        headers=DEV_HEADERS,
    )
    assert other.status_code == 201
    assert client.get(f"/text/jobs/{other.json()['id']}").status_code == 404


def test_submission_rate_limit_protects_the_public_endpoint(client: TestClient):
    statuses = [
        client.post("/text/jobs", json={"text": "rate limit check"}).status_code for _ in range(12)
    ]

    assert 429 in statuses
