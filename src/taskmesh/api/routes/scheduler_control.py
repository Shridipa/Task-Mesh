"""Scheduler control endpoints — pause, resume, status, and manual execution."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...engine import engine
from ..auth import require_admin

router = APIRouter()

# In-memory scheduler state (in production use Redis)
_scheduler_paused: bool = False
_scheduler_pause_event: asyncio.Event = asyncio.Event()
_scheduler_pause_event.set()  # not paused by default


@router.get("/status", response_model=dict[str, Any])
async def scheduler_status(
    _: str = Depends(require_admin),
):
    """Get scheduler status (running/paused, uptime, etc.)."""
    return {
        "status": "paused" if _scheduler_paused else "running",
        "paused": _scheduler_paused,
        "last_heartbeat": None,  # could be tracked via Redis
        "pending_jobs": (await engine.metrics()).scheduled,
    }


@router.post("/pause", response_model=dict[str, Any])
async def scheduler_pause(
    _: str = Depends(require_admin),
):
    """Pause the scheduler. Scheduled jobs won't be promoted to pending."""
    global _scheduler_paused
    _scheduler_paused = True
    _scheduler_pause_event.clear()
    return {"status": "paused"}


@router.post("/resume", response_model=dict[str, Any])
async def scheduler_resume(
    _: str = Depends(require_admin),
):
    """Resume the scheduler."""
    global _scheduler_paused
    _scheduler_paused = False
    _scheduler_pause_event.set()
    return {"status": "running"}


@router.post("/run-now", response_model=dict[str, Any])
async def scheduler_run_now(
    _: str = Depends(require_admin),
):
    """Manually trigger release of due scheduled jobs."""
    released = await engine.release_due_jobs()
    return {"released": released}


# Exported for use by the scheduler main loop
def is_paused() -> bool:
    return _scheduler_paused


def get_pause_event() -> asyncio.Event:
    return _scheduler_pause_event