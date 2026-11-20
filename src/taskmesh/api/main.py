"""FastAPI application for TaskMesh.

Exposes REST API endpoints for jobs, workers, metrics, and dashboard.
Includes CORS, authentication middleware, and OpenAPI documentation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from ..config import ConfigError, Settings, get_settings, redact_url
from ..logging_config import configure_logging, request_id_var
from ..version import __version__
from .dependencies import (
    create_schema,
    database_ready,
    dispose_engine,
    dispose_redis,
    redis_ready,
)
from .routes import (
    analysis,
    analytics,
    auth,
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


def ensure_no_embedded_background_loops(settings: Settings) -> None:
    """Refuse to start the worker or scheduler inside a serverless function.

    Vercel sets ``VERCEL`` for every deployment. A request-scoped function
    cannot host a polling loop: it would be frozen, duplicated across
    instances, and would execute jobs with no durability. Failing loudly at
    startup is the only safe behaviour when the deployment forgot to run those
    loops as separate services.
    """
    if os.getenv("VERCEL") and (settings.embedded_worker or settings.embedded_scheduler):
        raise ConfigError(
            "EMBEDDED_WORKER and EMBEDDED_SCHEDULER must both be false in a Vercel "
            "Function. Run `python -m taskmesh.worker` and "
            "`python -m taskmesh.scheduler` on a persistent host instead."
        )


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_no_embedded_background_loops(settings)
    configure_logging()
    logger.info(
        "Starting TaskMesh API",
        extra={
            "environment": settings.environment,
            "database": redact_url(settings.database_url),
            "embedded_worker": settings.embedded_worker,
            "embedded_scheduler": settings.embedded_scheduler,
        },
    )
    if settings.environment != "production":
        for key in settings.api_keys:
            if key.startswith("dev-"):
                logger.warning(
                    "Development API key is active; configure AUTH_API_KEYS before "
                    "exposing this deployment"
                )
                break

    await create_schema()

    async def _run_with_logging(name: str, coro):
        """Run a background coroutine and log any unexpected termination."""
        try:
            await coro
        except asyncio.CancelledError:
            logger.info("%s cancelled (shutting down)", name)
        except Exception:
            logger.exception("%s terminated unexpectedly", name)

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
        logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TaskMesh API",
    description=(
        "Distributed task processing platform — manage jobs, workers, queues, "
        "and dead-letter recovery."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_context(request: Request, call_next):
    """Assign a request id, enforce the body limit and log the request."""
    request_id = request.headers.get("x-request-id") or secrets.token_hex(8)
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        declared_length = request.headers.get("content-length")
        if (
            declared_length
            and declared_length.isdigit()
            and int(declared_length) > settings.max_request_bytes
        ):
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
                headers={**SECURITY_HEADERS, "X-Request-ID": request_id},
            )

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if request.url.path not in ("/health", "/ready"):
            logger.info(
                "Request handled",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                },
            )
        return response
    finally:
        request_id_var.reset(token)


# CORS is added last so it is the outermost middleware and also decorates error
# responses. Wildcard origins are never combined with credentials.
_cors_kwargs: dict[str, object] = {
    "allow_origins": list(settings.cors_origins),
    "allow_methods": ["GET", "POST", "DELETE", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type", "X-Request-ID", "X-Worker-Token"],
    "expose_headers": ["X-Request-ID"],
    "allow_credentials": False,
    "max_age": 600,
}
app.add_middleware(CORSMiddleware, **_cors_kwargs)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/auth", tags=["auth"])
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
    """Liveness: the process is up and serving requests."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def ready():
    """Readiness: required dependencies are reachable.

    The database is required; Redis is reported but only required in
    production, where rate limiting and the scheduler lock depend on it.
    """
    database_ok = await database_ready()
    redis_ok = await redis_ready()
    ready_now = database_ok and (redis_ok or not settings.redis_required)
    body = {
        "status": "ready" if ready_now else "degraded",
        "checks": {"database": database_ok, "redis": redis_ok},
        "environment": settings.environment,
    }
    if not ready_now:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)
    return body


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak internals to the client; log the details instead."""
    logger.error(
        "Unhandled error",
        extra={"method": request.method, "path": request.url.path},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
        headers=SECURITY_HEADERS,
    )


# ---------------------------------------------------------------------------
# OpenAPI customization
# ---------------------------------------------------------------------------
def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="TaskMesh API",
        version=__version__,
        description="Distributed task processing platform API.",
        routes=app.routes,
    )

    schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(
        {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Exchange an API key at POST /auth/token for a signed, "
                    "short-lived access token."
                ),
            },
            "WorkerToken": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Worker-Token",
                "description": "Shared worker secret for lease/complete/fail callbacks",
            },
        }
    )

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]
