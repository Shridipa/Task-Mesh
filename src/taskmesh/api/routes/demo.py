"""Honest demo endpoint: create real pending jobs for the real worker loop."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...engine import engine
from ...models import JobCreate
from ..auth import require_admin

router = APIRouter()


@router.post("/run", response_model=dict[str, Any])
async def run_demo(
    count: int = Query(1, ge=1, le=5),
    _: str = Depends(require_admin),
):
    """Submit pending demo jobs; workers must lease and process them normally.

    This endpoint never chooses or writes a job status. Every job is created
    through the same engine path as an ordinary API submission.
    """
    created = []
    for index in range(count):
        job = await engine.create_job(
            JobCreate(
                job_type="demo.process",
                payload={
                    "task_name": f"TaskMesh live demonstration {index + 1}",
                    "description": "A demonstration task handled by the TaskMesh worker loop.",
                },
                priority=5,
                tenant_id="demo",
                max_retries=0,
            )
        )
        created.append({"id": job["id"], "status": job["status"]})

    return {"created": created, "message": "Jobs submitted to the real TaskMesh queue."}
