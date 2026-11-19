"""Integration tests for job creation through the HTTP API and the engine."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from support import DEVELOPER_HEADERS

from taskmesh.main import app

SAMPLE_JOB = {
    "job_type": "email",
    "payload": {"to": "user@example.com"},
    "priority": 5,
    "tenant_id": "test_tenant",
}


@pytest.fixture(scope="module")
def client(clean_queue):
    with TestClient(app) as test_client:
        yield test_client


def test_create_job_persists_through_the_engine(client: TestClient):
    response = client.post("/jobs/", json=SAMPLE_JOB, headers=DEVELOPER_HEADERS)

    assert response.status_code == 201
    job_data = response.json()
    assert isinstance(job_data["id"], str)
    assert job_data["job_type"] == SAMPLE_JOB["job_type"]
    # A non-admin token is pinned to its own tenant, whatever it asks for.
    assert job_data["tenant_id"] == "default"
    assert job_data["status"] == "pending"

    fetched = client.get(f"/jobs/{job_data['id']}", headers=DEVELOPER_HEADERS)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == job_data["id"]


def test_rejects_invalid_job_payloads(client: TestClient):
    assert client.post("/jobs/", json={"payload": {}}, headers=DEVELOPER_HEADERS).status_code == 422
    assert (
        client.post(
            "/jobs/", json={"job_type": "x", "priority": 99}, headers=DEVELOPER_HEADERS
        ).status_code
        == 422
    )
