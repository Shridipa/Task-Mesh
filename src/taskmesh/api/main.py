"""FastAPI application for TaskMesh.

Exposes REST API endpoints for jobs, workers, metrics, and dashboard.
Includes CORS, auth middleware, and OpenAPI documentation.
"""

from __future__ import annotations

import logging
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from .auth import (
    require_worker_token as _require_worker_token,
)
from ..config import get_settings, redact_url
from .dependencies import create_schema, dispose_engine, dispose_redis
from .routes import (
    analysis,
    analytics,
    dashboard,
    events,
    jobs,
    logs,
    metrics,
    scheduler_control,
    text,
    workers,
)

logger = logging.getLogger(__name__)

settings = get_settings()

CORS_ORIGINS = ",".join(settings.cors_origins)
WORKER_SECRET = settings.worker_secret

require_worker_token = _require_worker_token(WORKER_SECRET)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting TaskMesh API",
        extra={
            "environment": settings.environment,
            "database": redact_url(settings.database_url),
            "embedded_worker": settings.embedded_worker,
            "embedded_scheduler": settings.embedded_scheduler,
        },
    )
    await create_schema()

    async def _run_with_logging(name: str, coro):
        """Run a background coroutine and log any unexpected termination."""
        try:
            await coro
        except asyncio.CancelledError:
            logger.info("%s cancelled (shutting down)", name)
        except Exception as exc:  # noqa: BLE001 - background loops may fail for many reasons
            logger.error("%s terminated unexpectedly: %s", name, exc, exc_info=True)

    tasks: list[asyncio.Task] = []
    # Local development runs everything in one process. Container deployments
    # set EMBEDDED_WORKER/EMBEDDED_SCHEDULER=false and run dedicated services.
    if settings.embedded_scheduler:
        from ..scheduler import main as scheduler_main

        scheduler_task = asyncio.create_task(_run_with_logging("scheduler", scheduler_main()))
        app.state.scheduler_task = scheduler_task
        tasks.append(scheduler_task)
    if settings.embedded_worker:
        from ..worker import main as worker_main

        worker_task = asyncio.create_task(_run_with_logging("worker", worker_main()))
        app.state.worker_task = worker_task
        tasks.append(worker_task)

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await dispose_engine()
        await dispose_redis()
        logger.info("Background tasks shut down")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TaskMesh API",
    description="Distributed task processing platform — manage jobs, workers, queues, and dead-letter recovery.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
allowed_origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(workers.router, prefix="/workers", tags=["workers"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(dashboard.router, prefix="", tags=["dashboard"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(scheduler_control.router, prefix="/scheduler", tags=["scheduler"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(text.router, prefix="/text", tags=["text"])
app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# OpenAPI customization
# ---------------------------------------------------------------------------
def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="TaskMesh API",
        version="0.1.0",
        description="Distributed task processing platform API.",
        routes=app.routes,
    )

    schema["components"]["securitySchemes"] = {
        "XRole": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Role",
            "description": "Role-based access: admin, developer, viewer",
        },
        "XWorkerToken": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Worker-Token",
            "description": "Worker authentication token",
        },
    }

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]
