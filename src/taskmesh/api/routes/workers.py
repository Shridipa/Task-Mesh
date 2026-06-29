"""Worker management endpoints — real data from the engine."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...engine import engine
from ...models import WorkerHeartbeat
from ..auth import require_worker, require_worker_token, require_read

router = APIRouter()


@router.get("/", response_model=list[dict[str, Any]])
async def list_workers(
    active: bool = Query(False, description="Filter to active workers only"),
    _: str = Depends(require_read),
):
    """List all workers with optional active-only filter."""
    workers = await engine.list_workers(active_only=active)
    # engine.list_workers already returns plain dicts; normalize datetime fields
    return [_serialize_worker(w) for w in workers]


@router.post("/heartbeat", response_model=dict[str, Any])
async def worker_heartbeat(
    heartbeat: WorkerHeartbeat,
    _role: str = Depends(require_worker),
    _token: str = Depends(require_worker_token),
):
    """Register a worker heartbeat. Requires worker role + valid token."""
    worker = await engine.heartbeat(heartbeat)
    # engine.heartbeat already returns a plain dict
    return _serialize_worker(worker)


def _serialize_worker(obj: dict[str, Any]) -> dict[str, Any]:
    """Normalize datetime fields in a worker dict for JSON serialization."""
    d = {}
    for key, val in obj.items():
        if hasattr(val, "isoformat"):
            d[key] = val.isoformat() if val else None
        else:
            d[key] = val
    return d
