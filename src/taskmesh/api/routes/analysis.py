"""Public analysis demo endpoints: JSON validation and CSV analysis.

Visitors submit a document without credentials. The route only creates a real
job of the requested analysis type through the normal engine path — it never
executes or completes anything itself. Lookups are restricted to analysis job
types so no other tenant data can be read through this public surface.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...csv_analysis import CSV_JOB_TYPE, MAX_CSV_LENGTH
from ...engine import engine
from ...json_validation import JSON_JOB_TYPE, MAX_JSON_LENGTH
from ...models import JobCreate
from ..rate_limit import SlidingWindowLimiter, client_key

router = APIRouter()

AnalysisTask = Literal["json.validate", "csv.analyze"]

ANALYSIS_JOB_TYPES = (JSON_JOB_TYPE, CSV_JOB_TYPE)
TASK_LIMITS = {JSON_JOB_TYPE: MAX_JSON_LENGTH, CSV_JOB_TYPE: MAX_CSV_LENGTH}
MAX_CONTENT_LENGTH = max(TASK_LIMITS.values())

_limiter = SlidingWindowLimiter(limit=10, window_seconds=60.0)


class AnalysisJobRequest(BaseModel):
    task: AnalysisTask
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)


@router.post("/jobs", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
async def submit_analysis_job(payload: AnalysisJobRequest, request: Request):
    """Queue a real analysis job (``json.validate`` or ``csv.analyze``)."""
    if not payload.content.strip():
        raise HTTPException(status_code=422, detail="Input must not be empty.")

    limit = TASK_LIMITS[payload.task]
    if len(payload.content) > limit:
        raise HTTPException(
            status_code=422,
            detail=f"{payload.task} accepts at most {limit:,} characters.",
        )

    _limiter.check(
        client_key(request),
        "Too many tasks submitted. Please wait a minute and try again.",
    )

    try:
        job = await engine.create_job(
            JobCreate(
                job_type=payload.task,
                payload={"content": payload.content},
                tenant_id="demo",
                priority=5,
                max_retries=2,
            )
        )
    except ValueError as exc:
        if str(exc) == "rate_limit_exceeded":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Task submission limit reached. Please try again shortly.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return job


@router.get("/jobs/{job_id}", response_model=dict[str, Any])
async def get_analysis_job(job_id: str):
    """Return the status (and result once finished) of an analysis job."""
    job = await engine.get_job(job_id)
    if job is None or job.get("job_type") not in ANALYSIS_JOB_TYPES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return job
