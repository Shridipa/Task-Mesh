"""Async scheduler for TaskMesh.

Releases scheduled jobs when their execute_at time arrives.
Uses Redis distributed locking for single-active-scheduler semantics when Redis is available.
Falls back to simple polling without locking when Redis is unavailable.
Implements lease expiry, heartbeat, and crash recovery.
"""

from __future__ import annotations

import asyncio
import os
import uuid
import logging

import redis.asyncio as redis

from src.taskmesh.engine import engine

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

logger = logging.getLogger(__name__)

_redis_available: bool | None = None


async def _check_redis() -> bool:
    """Check if Redis is reachable. Cache result to avoid hammering on each loop."""
    global _redis_available
    try:
        await redis_client.ping()
        _redis_available = True
        return True
    except Exception:
        if _redis_available is not False:
            logger.warning("Redis unavailable — scheduler running without distributed locking")
        _redis_available = False
        return False


async def _heartbeat_loop(scheduler_id: str, stop_event: asyncio.Event) -> None:
    """Periodically refresh the scheduler lock to signal liveness."""
    while not stop_event.is_set():
        if _redis_available:
            try:
                await redis_client.expire("scheduler_lock", 5)
            except Exception:
                pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
        except asyncio.TimeoutError:
            continue


async def main() -> None:
    scheduler_id = str(uuid.uuid4())
    logger.info(f"Starting scheduler {scheduler_id}")

    stop_event = asyncio.Event()

    # Check Redis availability
    await _check_redis()

    # Start heartbeat task
    heartbeat_task = asyncio.create_task(_heartbeat_loop(scheduler_id, stop_event))

    try:
        while True:
            try:
                lock_acquired = False

                if _redis_available:
                    # Acquire distributed lock (only one scheduler runs release logic)
                    lock_acquired = await redis_client.set(
                        "scheduler_lock", scheduler_id, nx=True, ex=5
                    )
                else:
                    # No Redis: always run (single-process mode)
                    lock_acquired = True

                if lock_acquired:
                    # Release scheduled jobs whose execute_at has arrived
                    released = await engine.release_due_jobs()
                    if released > 0:
                        logger.info(f"Released {released} due jobs")

                    # Mark workers as inactive if heartbeat expired
                    expired_workers = await engine.heartbeat_expired_workers()
                    if expired_workers > 0:
                        logger.info(f"Marked {expired_workers} workers as inactive")

                await asyncio.sleep(1)

            except Exception as exc:
                logger.error(f"Scheduler error: {exc}")
                await asyncio.sleep(5)
    finally:
        stop_event.set()
        await heartbeat_task
        if _redis_available:
            try:
                await redis_client.delete("scheduler_lock")
            except Exception:
                pass
        logger.info("Scheduler shut down gracefully")


if __name__ == "__main__":
    asyncio.run(main())
