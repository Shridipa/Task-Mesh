"""FastAPI application for TaskMesh."""

from __future__ import annotations
import logging, asyncio, os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from .auth import require_worker_token as _require_worker_token
from .dependencies import create_schema
from .routes import analytics,dashboard,events,jobs,logs,metrics,scheduler_control,text,workers,multi_tasks
logger=logging.getLogger(__name__)
CORS_ORIGINS=os.getenv("CORS_ORIGINS","*")
WORKER_SECRET=os.getenv("WORKER_SECRET","taskmesh_secret")
require_worker_token=_require_worker_token(WORKER_SECRET)
@asynccontextmanager
async def lifespan(app:FastAPI):
    logger.info("Creating database schema...")
    await create_schema()
    from ..scheduler import main as scheduler_main
    from ..worker import main as worker_main
    async def _run_with_logging(name,coro):
        try: await coro
        except asyncio.CancelledError: logger.info("%s cancelled (shutting down)",name)
        except Exception as exc: logger.error("%s terminated unexpectedly: %s",name,exc,exc_info=True)
    scheduler_task=asyncio.create_task(_run_with_logging("scheduler",scheduler_main()))
    worker_task=asyncio.create_task(_run_with_logging("worker",worker_main()))
    app.state.scheduler_task=scheduler_task;app.state.worker_task=worker_task
    try: yield
    finally:
        scheduler_task.cancel();worker_task.cancel()
        await asyncio.gather(scheduler_task,worker_task,return_exceptions=True)
        logger.info("Background tasks shut down")
app=FastAPI(title="TaskMesh API",description="Distributed task processing platform — manage jobs, workers, queues, and dead-letter recovery.",version="0.1.0",docs_url="/docs",redoc_url="/redoc",lifespan=lifespan)
allowed_origins=[o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(CORSMiddleware,allow_origins=allowed_origins if allowed_origins!=["*"] else ["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(jobs.router,prefix="/jobs",tags=["jobs"])
app.include_router(workers.router,prefix="/workers",tags=["workers"])
app.include_router(metrics.router,prefix="/metrics",tags=["metrics"])
app.include_router(dashboard.router,prefix="",tags=["dashboard"])
app.include_router(events.router,prefix="/events",tags=["events"])
app.include_router(scheduler_control.router,prefix="/scheduler",tags=["scheduler"])
app.include_router(analytics.router,prefix="/analytics",tags=["analytics"])
app.include_router(text.router,prefix="/text",tags=["text"])
app.include_router(multi_tasks.router,prefix="/analysis",tags=["multi-task analysis"])
app.include_router(logs.router,prefix="/logs",tags=["logs"])
@app.get("/health",tags=["system"])
async def health(): return {"status":"ok"}
def custom_openapi()->dict:
    if app.openapi_schema:return app.openapi_schema
    schema=get_openapi(title="TaskMesh API",version="0.1.0",description="Distributed task processing platform API.",routes=app.routes)
    schema["components"]["securitySchemes"]={"XRole":{"type":"apiKey","in":"header","name":"X-Role","description":"Role-based access: admin, developer, viewer"},"XWorkerToken":{"type":"apiKey","in":"header","name":"X-Worker-Token","description":"Worker authentication token"}}
    app.openapi_schema=schema;return schema
app.openapi=custom_openapi # type: ignore[method-assign]
