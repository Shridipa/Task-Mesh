"""Async worker process for TaskMesh.

Leases jobs from the engine, executes them with the handler registered for
their job type, and stores the result (or the failure) through the engine.
Sends a heartbeat on every loop so the dashboard shows live workers.

Failure handling distinguishes two cases:

* :class:`~taskmesh.errors.JobInputError` — the payload is invalid and will
  fail identically on every retry, so the job is failed permanently.
* Anything else — treated as a transient failure and retried with backoff up to
  ``max_retries`` before moving to the dead-letter queue.

Every completion/failure is reported with the worker id so the engine can
refuse writes from a worker whose lease has already expired.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import socket
import time

from .config import get_settings
from .engine import engine
from .errors import JobInputError, JobOwnershipError
from .liveness import touch_liveness
from .logging_config import configure_logging
from .models import WorkerHeartbeat
from .tasks import UnsupportedJobType, execute_job

logger = logging.getLogger(__name__)

ERROR_BACKOFF_SECONDS = 5.0


def _cpu_usage() -> float:
    """Current 1-minute load average as a percentage of available CPUs."""
    try:
        load = os.getloadavg()[0]
    except (OSError, AttributeError):
        return 0.0
    cpus = os.cpu_count() or 1
    return round(min(load / cpus * 100, 100.0), 1)


def _memory_usage() -> float:
    """Used system memory as a percentage (Linux ``/proc/meminfo``, else 0.0)."""
    try:
        values: dict[str, int] = {}
        with open("/proc/meminfo", encoding="ascii") as meminfo:
            for line in meminfo:
                name, _, rest = line.partition(":")
                if rest.strip():
                    values[name] = int(rest.split()[0])
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if not total or available is None:
            return 0.0
        return round((total - available) / total * 100, 1)
    except (OSError, ValueError, IndexError):
        return 0.0


async def run_worker(
    stop_event: asyncio.Event | None = None,
    *,
    max_jobs: int | None = None,
) -> int:
    """Run the worker loop until ``stop_event`` is set.

    Returns the number of jobs completed successfully. ``max_jobs`` bounds the
    number of jobs *handled* (completed, failed or retried), which keeps tests
    deterministic; production runs without a bound.
    """
    settings = get_settings()
    worker_id = os.getenv("WORKER_ID", socket.gethostname())
    interval = settings.job_poll_seconds
    stop_event = stop_event or asyncio.Event()
    current_job_id: str | None = None
    handled = 0
    processed = 0

    logger.info("Worker starting", extra={"worker_id": worker_id})

    while not stop_event.is_set():
        if max_jobs is not None and processed >= max_jobs:
            break
        touch_liveness(settings.worker_health_file)
        try:
            await engine.heartbeat(
                WorkerHeartbeat(
                    worker_id=worker_id,
                    hostname=socket.gethostname(),
                    cpu_usage=_cpu_usage(),
                    memory_usage=_memory_usage(),
                    active_jobs=1 if current_job_id is not None else 0,
                )
            )

            job = await engine.lease_next_job(worker_id)
            if job is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                continue

            job_id = str(job["id"])
            job_type = job["job_type"]
            current_job_id = job_id
            started = time.perf_counter()
            logger.info(
                "Job started",
                extra={"worker_id": worker_id, "job_id": job_id, "job_type": job_type},
            )

            try:
                result = execute_job(job_type, job.get("payload") or {})
            except (JobInputError, UnsupportedJobType) as exc:
                # Deterministic failures: retrying would reproduce them.
                current_job_id = None
                logger.warning(
                    "Job rejected",
                    extra={
                        "worker_id": worker_id,
                        "job_id": job_id,
                        "job_type": job_type,
                        "status": "failed",
                    },
                )
                await engine.fail_job(job_id, str(exc), retryable=False, worker_id=worker_id)
            except JobOwnershipError as exc:
                current_job_id = None
                logger.warning("Lease lost before failure: %s", exc)
            except Exception as exc:  # noqa: BLE001 - any handler error is a job failure
                current_job_id = None
                logger.warning(
                    "Job failed",
                    extra={
                        "worker_id": worker_id,
                        "job_id": job_id,
                        "job_type": job_type,
                        "status": "retrying",
                    },
                )
                try:
                    await engine.fail_job(job_id, str(exc), worker_id=worker_id)
                except JobOwnershipError as ownership_exc:
                    logger.warning("Lease lost before failure: %s", ownership_exc)
            else:
                current_job_id = None
                duration_ms = round((time.perf_counter() - started) * 1000, 1)
                try:
                    await engine.complete_job(job_id, result, worker_id=worker_id)
                except JobOwnershipError as exc:
                    logger.warning("Lease lost before completion: %s", exc)
                else:
                    handled += 1
                    logger.info(
                        "Job completed",
                        extra={
                            "worker_id": worker_id,
                            "job_id": job_id,
                            "job_type": job_type,
                            "duration_ms": duration_ms,
                            "status": "completed",
                        },
                    )

            processed += 1

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Worker error: %s", exc)
            if current_job_id is not None:
                try:
                    await engine.fail_job(current_job_id, str(exc), worker_id=worker_id)
                except Exception as inner:  # noqa: BLE001 - log and keep polling
                    logger.error("Failed to mark job %s as failed: %s", current_job_id, inner)
                current_job_id = None
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=ERROR_BACKOFF_SECONDS)
            except TimeoutError:
                continue

    logger.info(
        "Worker stopped",
        extra={"worker_id": worker_id, "jobs_handled": handled, "jobs_processed": processed},
    )
    return handled


async def main() -> None:
    """Entrypoint used by ``python -m taskmesh.worker``."""
    # A standalone worker host (Render, a container) has no API lifespan to
    # configure logging, so do it here before the first log line.
    configure_logging(service="taskmesh-worker")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        logger.info("Shutdown signal received; finishing the current job first")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        # Windows and non-main threads (e.g. TestClient's lifespan) cannot
        # install signal handlers; that is fine, shutdown still works.
        with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
            loop.add_signal_handler(sig, _request_stop)

    await run_worker(stop_event)


if __name__ == "__main__":
    asyncio.run(main())
