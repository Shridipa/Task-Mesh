"""Analytics endpoints — time-series data for charts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...engine import engine
from ..auth import require_read

router = APIRouter()


@router.get("/time-series", response_model=list[dict[str, Any]])
async def analytics_time_series(
    hours: int = Query(24, ge=1, le=168),
    _: str = Depends(require_read),
):
    """Return time-series job data for analytics charts.

    Groups jobs by hour for the last N hours, broken down by status.
    """
    return await engine.analytics_time_series(hours=hours)
