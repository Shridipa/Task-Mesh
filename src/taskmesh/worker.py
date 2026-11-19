"""Async worker process for TaskMesh.

Leases jobs from the engine, executes them with the handler registered for
their job type, and stores the result (or the failure) through the engine.
Sends a heartbeat on every loop so the dashboard shows live workers.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

from .engine import engine
from .errors import JobInputError
from .models import WorkerHeartbeat
from .tasks import execute_job

logger = logging.getLogger(__name__)

IDLE_POLL_SECONDS = 1.0
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


async def main() -> None:
    worker_id = os.getenv("WORKER_ID", socket.gethostname())
    logger.info("Starting worker %s", worker_id)
    current_job_id: str | None = None

    while True:
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
                await asyncio.sleep(IDLE_POLL_SECONDS)
                continue

            job_id = str(job["id"])
            current_job_id = job_id
            logger.info("Worker %s executing %s job %s", worker_id, job["job_type"], job_id)

            try:
                result = execute_job(job["job_type"], job.get("payload") or {})
            except JobInputError as exc:
                # Invalid payloads fail the same way every time, so retrying is pointless.
                current_job_id = None
                logger.warning("Job %s rejected: %s", job_id, exc)
                await engine.fail_job(job_id, str(exc), retryable=False)
            except Exception as exc:  # noqa: BLE001 - any handler error is a job failure
                current_job_id = None
                logger.warning("Job %s failed: %s", job_id, exc)
                await engine.fail_job(job_id, str(exc))
            else:
                current_job_id = None
                await engine.complete_job(job_id, result)
                logger.info("Worker %s completed job %s", worker_id, job_id)

        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the worker loop alive
            logger.error("Worker error: %s", exc)
            if current_job_id is not None:
                try:
                    await engine.fail_job(current_job_id, str(exc))
                    logger.info("Worker failed job %s: %s", current_job_id, exc)
                except Exception as inner:  # noqa: BLE001 - log and keep polling
                    logger.error("Failed to mark job %s as failed: %s", current_job_id, inner)
                current_job_id = None
            await asyncio.sleep(ERROR_BACKOFF_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
