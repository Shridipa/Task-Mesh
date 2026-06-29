"""Event management endpoints — real data from the engine."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...engine import engine
from ..auth import require_read

router = APIRouter()


@router.get("/", response_model=list[dict[str, Any]])
async def list_events(
    job_id: str | None = Query(None),
    tenant_id: str | None = Query(None),
    event_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: str = Depends(require_read),
):
    """List events with optional filtering."""
    events = await engine.list_events(
        job_id=job_id,
        tenant_id=tenant_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return events
