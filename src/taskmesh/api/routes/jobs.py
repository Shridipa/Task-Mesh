"""Job management endpoints.

Job data is tenant-scoped: a token may only read and mutate jobs belonging to
its own tenant unless it carries the ``admin`` role. Worker callbacks
(lease/complete/fail) authenticate with the shared worker secret instead of a
user token.

Uses TaskMeshEngine for all operations (no in-memory fallback).
All job IDs are UUID strings.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ...engine import engine
from ...errors import JobOwnershipError
from ...models import JobCreate
from ..auth import (
    Principal,
    require_admin,
    require_read,
    require_worker_token,
    require_write,
    tenant_scope,
    worker_identity,
)
from ..dependencies import get_db, get_redis

router = APIRouter()

#: Returned instead of 403 so the existence of another tenant's job is not disclosed.
_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


def _ensure_visible(job: dict[str, Any] | None, principal: Principal) -> dict[str, Any]:
    """Raise 404 when the job is missing or belongs to another tenant."""
    if job is None:
        raise _NOT_FOUND
    if not principal.is_admin and job.get("tenant_id") != principal.tenant:
        raise _NOT_FOUND
    return job


@router.post("/", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_job(
    job: JobCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    principal: Principal = Depends(require_write),
):
    """Create a new job. Requires admin or developer role."""
    if not principal.is_admin:
        # A non-admin cannot create work for another tenant.
        job = job.model_copy(update={"tenant_id": principal.tenant})
    return await engine.create_job(job)


@router.get("/", response_model=list[dict[str, Any]])
async def list_jobs(
    status_filter: str | None = Query(None, alias="status"),
    tenant_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_read),
):
    """List jobs with optional filtering and pagination."""
    return await engine.list_jobs(
        status_filter=status_filter,
        tenant_id=tenant_scope(principal, tenant_id),
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=dict[str, Any])
async def get_job(
    job_id: str,
    principal: Principal = Depends(require_read),
):
    """Get a single job by ID (UUID string)."""
    return _ensure_visible(await engine.get_job(job_id), principal)


@router.post("/{job_id}/lease", response_model=dict[str, Any])
async def lease_job(
    job_id: str,
    _token: str = Depends(require_worker_token),
    worker_id: str = Depends(worker_identity),
):
    """Lease a job for execution. Requires the worker token."""
    job = await engine.lease_job_by_id(job_id, worker_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not available")
    return job


@router.post("/{job_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
async def complete_job(
    job_id: str,
    _token: str = Depends(require_worker_token),
    worker_id: str = Depends(worker_identity),
):
    """Mark a job as completed (worker only)."""
    try:
        await engine.complete_job(job_id, None, worker_id=worker_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    except JobOwnershipError:
        raise HTTPException(
            status_code=409, detail="This worker no longer holds the job lease"
        ) from None


@router.post("/{job_id}/fail", response_model=dict[str, Any])
async def fail_job(
    job_id: str,
    reason: str = Query("unknown error"),
    _token: str = Depends(require_worker_token),
    worker_id: str = Depends(worker_identity),
):
    """Fail a job. Moves to DLQ after max retries. Worker only."""
    try:
        return await engine.fail_job(job_id, reason, worker_id=worker_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    except JobOwnershipError:
        raise HTTPException(
            status_code=409, detail="This worker no longer holds the job lease"
        ) from None


@router.post("/{job_id}/replay", response_model=dict[str, Any])
async def replay_job(
    job_id: str,
    _: Principal = Depends(require_admin),
):
    """Replay a dead-letter job. Resets to pending. Admin only."""
    try:
        return await engine.replay_dead_letter(job_id)
    except KeyError:
        raise _NOT_FOUND from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post(
    "/{job_id}/duplicate", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any]
)
async def duplicate_job(
    job_id: str,
    principal: Principal = Depends(require_write),
):
    """Duplicate a job. Creates a new job with same type/payload/priority."""
    _ensure_visible(await engine.get_job(job_id), principal)
    try:
        return await engine.duplicate_job(job_id)
    except KeyError:
        raise _NOT_FOUND from None


@router.post("/{job_id}/cancel", response_model=dict[str, Any])
async def cancel_job(
    job_id: str,
    principal: Principal = Depends(require_write),
):
    """Cancel a pending or scheduled job. Requires admin or developer."""
    _ensure_visible(await engine.get_job(job_id), principal)
    try:
        return await engine.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except KeyError:
        raise _NOT_FOUND from None


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    principal: Principal = Depends(require_admin),
):
    """Delete a job. Admin only."""
    _ensure_visible(await engine.get_job(job_id), principal)
    await engine.delete_job(job_id)
