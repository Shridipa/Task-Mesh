"""Async worker process for TaskMesh.

Leases and executes jobs from the PostgreSQL/SQLite-backed engine.
Uses asyncio for non-blocking operation and proper async engine calls.
Registers heartbeat on startup and continuously polls for pending jobs.
"""
from __future__ import annotations

import asyncio
import os
import random
import socket
import logging

from .engine import engine
from .models import WorkerHeartbeat

logger = logging.getLogger(__name__)

# Track the current job being processed for error recovery
_current_job_id: str | None = None


async def main() -> None:
    global _current_job_id
    worker_id = os.getenv("WORKER_ID", socket.gethostname())
    logger.info(f"Starting worker {worker_id}")

    while True:
        try:
            # Send heartbeat (registers/updates worker in DB)
            await engine.heartbeat(
                WorkerHeartbeat(
                    worker_id=worker_id,
                    hostname=socket.gethostname(),
                    cpu_usage=random.uniform(10, 75),
                    memory_usage=random.uniform(20, 80),
                    active_jobs=1 if _current_job_id is not None else 0,
                )
            )

            # Lease next pending job
            job = await engine.lease_next_job(worker_id)
            if job is None:
                await asyncio.sleep(1)
                continue

            # Track the job for error recovery
            _current_job_id = str(job["id"])

            # Execute job (simulated work)
            logger.info(f"Worker {worker_id} executing job {_current_job_id}")
            await asyncio.sleep(random.uniform(0.05, 0.25))

            # Mark job as completed
            await engine.complete_job(_current_job_id)
            logger.info(f"Worker {worker_id} completed job {_current_job_id}")
            _current_job_id = None

        except Exception as exc:
            logger.error(f"Worker error: {exc}")
            # Attempt to fail the job if we had one
            if _current_job_id is not None:
                try:
                    await engine.fail_job(_current_job_id, str(exc))
                    logger.info(f"Worker failed job {_current_job_id}: {exc}")
                except Exception as inner:
                    logger.error(f"Failed to mark job {_current_job_id} as failed: {inner}")
                _current_job_id = None
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())