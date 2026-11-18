"""Public text-processing demo endpoints.

Visitors submit text here without credentials. The route only creates a real
``text.process`` job through the normal engine path and reads back the status of
that specific job — it never completes a job itself, execution happens in the
worker. Lookups are restricted to ``text.process`` jobs so no other tenant data
can be read through this public surface.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...engine import engine
from ...models import JobCreate
from ...text_processing import MAX_TEXT_LENGTH, TEXT_JOB_TYPE

router = APIRouter()

SUBMISSIONS_PER_WINDOW = 10
SUBMIT_WINDOW_SECONDS = 60.0
MAX_TRACKED_CLIENTS = 1024

_submissions: dict[str, deque[float]] = {}


class TextJobRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(key: str) -> None:
    """Allow a small number of submissions per client per minute."""
    now = time.monotonic()

    if len(_submissions) > MAX_TRACKED_CLIENTS:
        for stale in [client for client, window in _submissions.items() if not window]:
            del _submissions[stale]

    window = _submissions.setdefault(key, deque())
    while window and now - window[0] > SUBMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= SUBMISSIONS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many tasks submitted. Please wait a minute and try again.",
        )
    window.append(now)


@router.post("/jobs", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
async def submit_text_job(payload: TextJobRequest, request: Request):
    """Queue a real text-processing job and return it."""
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Text must not be empty.")

    _check_rate_limit(_client_key(request))

    try:
        job = await engine.create_job(
            JobCreate(
                job_type=TEXT_JOB_TYPE,
                payload={"text": payload.text},
                tenant_id="demo",
                priority=5,
                max_retries=3,
            )
        )
    except ValueError as exc:
        if str(exc) == "rate_limit_exceeded":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Task submission limit reached. Please try again shortly.",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return job


@router.get("/jobs/{job_id}", response_model=dict[str, Any])
async def get_text_job(job_id: str):
    """Return the status (and result once finished) of a submitted text job."""
    job = await engine.get_job(job_id)
    if job is None or job.get("job_type") != TEXT_JOB_TYPE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return job
