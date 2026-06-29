"""Metrics endpoints — real data and Prometheus output."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ...engine import engine
from ..auth import require_read

router = APIRouter()


@router.get("/summary", response_model=dict)
async def metrics_summary(
    _: str = Depends(require_read),
):
    """Return a JSON summary of system metrics.

    Uses the engine to aggregate counts from PostgreSQL.
    """
    m = await engine.metrics()
    return {
        "pending": m.pending,
        "scheduled": m.scheduled,
        "running": m.running,
        "completed": m.completed,
        "failed": m.failed,
        "dead_letter": m.dead_letter,
        "active_workers": m.active_workers,
        "throughput_per_minute": m.throughput_per_minute,
        "retry_rate": m.retry_rate,
    }


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics(
    _: str = Depends(require_read),
):
    """Return Prometheus-formatted metrics."""
    m = await engine.metrics()
    lines = [
        "# HELP taskmesh_queue_depth Current number of jobs in the queue",
        "# TYPE taskmesh_queue_depth gauge",
        f"taskmesh_queue_depth {m.pending + m.scheduled}",
        "",
        "# HELP taskmesh_jobs_completed_total Total completed jobs",
        "# TYPE taskmesh_jobs_completed_total counter",
        f"taskmesh_jobs_completed_total {m.completed}",
        "",
        "# HELP taskmesh_jobs_failed_total Total failed jobs",
        "# TYPE taskmesh_jobs_failed_total counter",
        f"taskmesh_jobs_failed_total {m.failed}",
        "",
        "# HELP taskmesh_active_workers Current active workers",
        "# TYPE taskmesh_active_workers gauge",
        f"taskmesh_active_workers {m.active_workers}",
        "",
        "# HELP taskmesh_retry_rate Current retry rate",
        "# TYPE taskmesh_retry_rate gauge",
        f"taskmesh_retry_rate {m.retry_rate}",
    ]
    return "\n".join(lines) + "\n"
