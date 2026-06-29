"""Dashboard endpoints — real metrics from the engine."""
from __future__ import annotations

from fastapi import APIRouter

from ...engine import engine
from ...models import Metrics

router = APIRouter()


@router.get("/dashboard/metrics", response_model=Metrics)
async def dashboard_metrics():
    """Return real-time dashboard metrics from the engine.

    Includes job counts by status, active workers, throughput, and retry rate.
    """
    return await engine.metrics()
