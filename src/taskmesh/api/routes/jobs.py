"""Job management endpoints.

Uses TaskMeshEngine for all operations (no in-memory fallback).
All job IDs are UUID strings.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from ...engine import engine
from ...models import JobCreate
from ..dependencies import get_db, get_redis
from ..auth import require_write, require_read, require_admin, require_worker, require_worker_token

router = APIRouter()


@router.post("/", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_job(
    job: JobCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _: str = Depends(require_write),
):
    """Create a new job. Requires admin or developer role."""
    return await engine.create_job(job)


@router.get("/", response_model=list[dict[str, Any]])
async def list_jobs(
    status_filter: str | None = Query(None, alias="status"),
    tenant_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: str = Depends(require_read),
):
    """List jobs with optional filtering and pagination."""
    return await engine.list_jobs(
        status_filter=status_filter,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=dict[str, Any])
async def get_job(
    job_id: str,
    _: str = Depends(require_read),
):
    """Get a single job by ID (UUID string)."""
    job = await engine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/lease", response_model=dict[str, Any])
async def lease_job(
    job_id: str,
    _worker: str = Depends(require_worker),
    _token: str = Depends(require_worker_token),
):
    """Lease a job for execution. Requires worker role + valid token."""
    job = await engine.lease_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not available")
    return job


@router.post("/{job_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
async def complete_job(
    job_id: str,
    _worker: str = Depends(require_worker),
    _token: str = Depends(require_worker_token),
):
    """Mark a job as completed (worker only)."""
    await engine.complete_job(job_id)
    return None


@router.post("/{job_id}/fail", response_model=dict[str, Any])
async def fail_job(
    job_id: str,
    reason: str = Query("unknown error"),
    _worker: str = Depends(require_worker),
    _token: str = Depends(require_worker_token),
):
    """Fail a job. Moves to DLQ after max retries. Worker only."""
    return await engine.fail_job(job_id, reason)


@router.post("/{job_id}/replay", response_model=dict[str, Any])
async def replay_job(
    job_id: str,
    _: str = Depends(require_admin),
):
    """Replay a dead-letter job. Resets to pending. Admin only."""
    return await engine.replay_dead_letter(job_id)


@router.post(
    "/{job_id}/duplicate", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any]
)
async def duplicate_job(
    job_id: str,
    _: str = Depends(require_write),
):
    """Duplicate a job. Creates a new job with same type/payload/priority. Requires admin or developer."""
    try:
        return await engine.duplicate_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/{job_id}/cancel", response_model=dict[str, Any])
async def cancel_job(
    job_id: str,
    _: str = Depends(require_admin),
):
    """Cancel a pending or scheduled job. Admin only."""
    try:
        return await engine.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    _: str = Depends(require_admin),
):
    """Delete a job. Admin only."""
    await engine.delete_job(job_id)
    return None
