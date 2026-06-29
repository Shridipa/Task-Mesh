"""Logs endpoint — returns recent events formatted as log entries."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...engine import engine
from ..auth import require_read

router = APIRouter()


@router.get("/", response_model=list[dict[str, Any]])
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_type: str | None = Query(None),
    job_id: str | None = Query(None),
    _: str = Depends(require_read),
):
    """Get recent log entries (events formatted as logs).
    
    Supports filtering by event_type and job_id.
    Poll this endpoint for live log updates.
    """
    events = await engine.list_events(
        event_type=event_type,
        job_id=job_id,
        limit=limit,
        offset=offset,
    )
    
    # Format events as log entries
    logs = []
    for event in events:
        created = event.get("created_at", "")
        if isinstance(created, str):
            # Extract time portion for display
            time_str = created.split("T")[1][:8] if "T" in created else created[:8]
        else:
            time_str = str(created)[:8]
        
        logs.append({
            "timestamp": time_str,
            "level": _event_to_level(event.get("event_type", "")),
            "source": "engine",
            "job_id": event.get("job_id"),
            "message": event.get("message", ""),
            "event_type": event.get("event_type"),
        })
    
    return logs


def _event_to_level(event_type: str) -> str:
    """Map event types to log levels."""
    if "Error" in event_type or "Failed" in event_type or "DeadLetter" in event_type:
        return "ERROR"
    if "Retry" in event_type or "Cancel" in event_type:
        return "WARNING"
    if "Completed" in event_type:
        return "SUCCESS"
    if "Started" in event_type or "Created" in event_type or "Assigned" in event_type:
        return "INFO"
    return "INFO"