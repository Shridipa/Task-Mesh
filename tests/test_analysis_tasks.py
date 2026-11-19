"""Tests for the analysis workloads: pure logic, dispatch, API and real worker runs."""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from taskmesh.csv_analysis import CSV_JOB_TYPE, MAX_CSV_LENGTH, analyze_csv
from taskmesh.errors import JobInputError
from taskmesh.json_validation import JSON_JOB_TYPE, MAX_JSON_LENGTH, validate_json
from taskmesh.main import app
from taskmesh.tasks import UnsupportedJobType, execute_job

DEV_HEADERS = {"X-Role": "developer"}

JSON_DOCUMENT = """{
  "name": "TaskMesh",
  "tags": ["queue", "worker"],
  "nested": {"depth": 2, "flag": true, "missing": null},
  "count": 3.5
}"""

CSV_DOCUMENT = 'name,score,note\nAda,90,"likes, commas"\nGrace,80,first\nAda,90,"likes, commas"\nLinus,,third\n'


@pytest.fixture(scope="module")
def client(clean_queue):
    with TestClient(app) as test_client:
        yield test_client


def _wait_for_terminal_status(client: TestClient, path: str, timeout: float = 25.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(path)
        assert response.status_code == 200
        last = response.json()
        if last["status"] in {"completed", "failed", "dead_letter", "canceled"}:
            return last
        time.sleep(0.2)
    raise AssertionError(f"job never reached a terminal status: {last}")


# ---------------------------------------------------------------------------
# JSON validation rules
# ---------------------------------------------------------------------------
def test_validate_json_reports_structure_and_formatted_output():
    result = validate_json(JSON_DOCUMENT)

    assert result["valid"] is True
    assert result["root_type"] == "object"
    assert result["counts"] == {
        "objects": 2,
        "arrays": 1,
        "keys": 7,
        "strings": 3,
        "numbers": 2,
        "booleans": 1,
        "nulls": 1,
    }
    assert result["max_depth"] == 3
    assert result["formatted"].startswith('{\n  "name": "TaskMesh",')
    assert '\n  "tags": [\n    "queue",\n    "worker"\n  ],' in result["formatted"]
    assert result["formatted"].endswith('"count": 3.5\n}')


@pytest.mark.parametrize(
    ("document", "root_type"),
    [
        ("[1, 2, 3]", "array"),
        ('"just a string"', "string"),
        ("42", "number"),
        ("false", "boolean"),
        ("null", "null"),
    ],
)
def test_validate_json_accepts_every_root_type(document: str, root_type: str):
    assert validate_json(document)["root_type"] == root_type


def test_validate_json_preserves_unicode():
    result = validate_json('{"greeting": "héllo 日本語"}')

    assert result["valid"] is True
    assert "héllo 日本語" in result["formatted"]


def test_validate_json_reports_line_and_column_for_invalid_input():
    with pytest.raises(JobInputError) as excinfo:
        validate_json('{\n  "a": 1,\n  "b": 2,\n}')

    message = str(excinfo.value)
    assert message.startswith("Invalid JSON at line 4, column 1")
    assert "column" in message


@pytest.mark.parametrize(
    "document",
    [
        "{",
        '{"a": 1',
        "[1, 2",
        '{"a": 1 "b": 2}',
        "{'a': 1}",
        '{"a": 1,}',
        "NaN",
        "Infinity",
    ],
)
def test_validate_json_rejects_malformed_documents(document: str):
    with pytest.raises(JobInputError):
        validate_json(document)


def test_validate_json_rejects_empty_and_oversized_input():
    with pytest.raises(JobInputError):
        validate_json("   \n ")
    with pytest.raises(JobInputError):
        validate_json("[" + "1," * MAX_JSON_LENGTH + "1]")


def test_validate_json_handles_deep_nesting_without_recursion_errors():
    result = validate_json("[" * 200 + "]" * 200)

    assert result["valid"] is True
    assert result["max_depth"] == 200


# ---------------------------------------------------------------------------
# CSV analysis rules
# ---------------------------------------------------------------------------
def test_analyze_csv_reports_shape_missing_and_duplicates():
    result = analyze_csv(CSV_DOCUMENT)

    assert result["rows"] == 4
    assert result["columns"] == 3
    assert result["column_names"] == ["name", "score", "note"]
    assert result["missing_values"] == {"total": 1, "by_column": {"name": 0, "score": 1, "note": 0}}
    assert result["duplicate_rows"] == 1
    assert result["ragged_rows"] == 0


def test_analyze_csv_computes_numeric_statistics():
    result = analyze_csv(CSV_DOCUMENT)

    assert result["numeric_columns"] == ["score"]
    assert result["statistics"]["score"] == {
        "count": 3,
        "mean": round((90 + 80 + 90) / 3, 6),
        "median": 90,
        "min": 80,
        "max": 90,
    }


def test_analyze_csv_supports_quoted_fields_with_commas_quotes_and_newlines():
    document = 'id,comment\n1,"a, b"\n2,"say ""hi"""\n3,"line one\nline two"\n'
    result = analyze_csv(document)

    assert result["rows"] == 3
    assert result["preview"][1] == {"id": "2", "comment": 'say "hi"'}
    assert result["preview"][2] == {"id": "3", "comment": "line one\nline two"}
    assert result["numeric_columns"] == ["id"]


def test_analyze_csv_reports_extra_fields_and_blank_headers():
    result = analyze_csv("a,,a\n1,2,3,extra\n4,5,6\n")

    assert result["column_names"] == ["a", "column_2", "a_2"]
    assert result["columns"] == 3
    assert result["ragged_rows"] == 1
    assert result["rows"] == 2


def test_analyze_csv_accepts_a_header_without_rows():
    result = analyze_csv("a,b\n")

    assert result["rows"] == 0
    assert result["columns"] == 2
    assert result["column_names"] == ["a", "b"]
    assert result["numeric_columns"] == []


def test_analyze_csv_rejects_empty_malformed_and_oversized_input():
    with pytest.raises(JobInputError):
        analyze_csv("  \n ")
    with pytest.raises(JobInputError) as excinfo:
        analyze_csv('a,b\n"unterminated,1\n')
    assert "near line" in str(excinfo.value)
    with pytest.raises(JobInputError):
        analyze_csv("a\n" + "1\n" * MAX_CSV_LENGTH)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
def test_execute_job_dispatches_both_analysis_handlers():
    assert execute_job(JSON_JOB_TYPE, {"content": "[1]"} )["root_type"] == "array"
    assert execute_job(CSV_JOB_TYPE, {"content": "a\n1\n"})["rows"] == 1


def test_execute_job_rejects_bad_payloads_and_unknown_types():
    with pytest.raises(JobInputError):
        execute_job(JSON_JOB_TYPE, {})
    with pytest.raises(JobInputError):
        execute_job(CSV_JOB_TYPE, {"content": 42})
    with pytest.raises(UnsupportedJobType):
        execute_job("image.resize", {"content": "x"})


# ---------------------------------------------------------------------------
# HTTP API and end-to-end execution
# ---------------------------------------------------------------------------
def test_submit_json_job_runs_in_the_worker(client: TestClient):
    created = client.post("/analysis/jobs", json={"task": JSON_JOB_TYPE, "content": JSON_DOCUMENT})
    assert created.status_code == 201
    job = created.json()
    assert job["job_type"] == JSON_JOB_TYPE
    assert job["result"] is None

    finished = _wait_for_terminal_status(client, f"/analysis/jobs/{job['id']}")

    assert finished["status"] == "completed"
    assert finished["worker_id"]
    assert finished["result"]["root_type"] == "object"
    assert finished["result"]["counts"]["objects"] == 2


def test_invalid_json_fails_the_job_once_with_line_and_column(client: TestClient):
    created = client.post("/analysis/jobs", json={"task": JSON_JOB_TYPE, "content": '{"a": }'})
    assert created.status_code == 201

    finished = _wait_for_terminal_status(client, f"/analysis/jobs/{created.json()['id']}")

    assert finished["status"] == "failed"
    assert finished["result"] is None
    assert finished["retry_count"] >= 1
    assert "Invalid JSON at line 1" in finished["failure_reason"]
    assert "column" in finished["failure_reason"]


def test_submit_csv_job_runs_in_the_worker(client: TestClient):
    created = client.post("/analysis/jobs", json={"task": CSV_JOB_TYPE, "content": CSV_DOCUMENT})
    assert created.status_code == 201

    finished = _wait_for_terminal_status(client, f"/analysis/jobs/{created.json()['id']}")

    assert finished["status"] == "completed"
    assert finished["result"]["rows"] == 4
    assert finished["result"]["columns"] == 3
    assert finished["result"]["missing_values"]["total"] == 1
    assert finished["result"]["duplicate_rows"] == 1
    assert finished["result"]["statistics"]["score"]["max"] == 90


def test_analysis_api_validates_requests_and_hides_other_jobs(client: TestClient):
    assert client.post("/analysis/jobs", json={"task": JSON_JOB_TYPE, "content": "   "}).status_code == 422
    assert client.post("/analysis/jobs", json={"task": "text.process", "content": "x"}).status_code == 422
    assert (
        client.post(
            "/analysis/jobs",
            json={"task": JSON_JOB_TYPE, "content": "[" + "1," * MAX_JSON_LENGTH + "1]"},
        ).status_code
        == 422
    )
    assert client.get(f"/analysis/jobs/{uuid.uuid4()}").status_code == 404

    text_job = client.post("/text/jobs", json={"text": "not an analysis job"}).json()
    assert client.get(f"/analysis/jobs/{text_job['id']}").status_code == 404

    other = client.post(
        "/jobs/",
        json={"job_type": "email", "payload": {"to": "user@example.com"}},
        headers=DEV_HEADERS,
    )
    assert other.status_code == 201
    assert client.get(f"/analysis/jobs/{other.json()['id']}").status_code == 404


def test_analysis_submissions_are_rate_limited(client: TestClient):
    statuses = [
        client.post("/analysis/jobs", json={"task": JSON_JOB_TYPE, "content": "{}"}).status_code
        for _ in range(12)
    ]

    assert 429 in statuses
