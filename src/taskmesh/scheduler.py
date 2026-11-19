"""Async scheduler for TaskMesh.

Releases scheduled jobs when their ``execute_at`` time arrives and requeues jobs
whose worker lease expired so a crashed worker cannot strand them forever.

Uses a Redis distributed lock for single-active-scheduler semantics when Redis
is available, and falls back to simple polling without locking when it is not
(single-process development).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid

import redis.asyncio as redis

from .config import get_settings
from .engine import engine

logger = logging.getLogger(__name__)

POLL_SECONDS = 1.0
ERROR_BACKOFF_SECONDS = 5.0
LOCK_TTL_SECONDS = 5


class _RedisState:
    """Cached Redis availability, refreshed on every loop iteration."""

    def __init__(self, client: redis.Redis) -> None:
        self.client = client
        self.available: bool | None = None

    async def check(self) -> bool:
        try:
            await self.client.ping()
        except Exception as exc:  # noqa: BLE001 - redis-py raises many error types
            if self.available is not False:
                logger.warning(
                    "Redis unavailable (%s) — scheduler running without distributed locking",
                    type(exc).__name__,
                )
            self.available = False
            return False
        self.available = True
        return True


async def _heartbeat_loop(state: _RedisState, scheduler_id: str, stop_event: asyncio.Event) -> None:
    """Periodically refresh the scheduler lock to signal liveness."""
    while not stop_event.is_set():
        if state.available:
            try:
                await state.client.expire("scheduler_lock", LOCK_TTL_SECONDS)
            except Exception as exc:  # noqa: BLE001 - lock refresh is best effort
                logger.debug("Scheduler lock refresh failed: %s", type(exc).__name__)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
        except TimeoutError:
            continue


async def run_scheduler(stop_event: asyncio.Event | None = None) -> None:
    """Run one scheduler loop until ``stop_event`` is set."""
    settings = get_settings()
    scheduler_id = str(uuid.uuid4())
    stop_event = stop_event or asyncio.Event()
    state = _RedisState(redis.from_url(settings.redis_url, decode_responses=True))

    logger.info("Scheduler starting", extra={"scheduler_id": scheduler_id})
    await state.check()
    heartbeat_task = asyncio.create_task(_heartbeat_loop(state, scheduler_id, stop_event))

    try:
        while not stop_event.is_set():
            try:
                if state.available:
                    lock_acquired = await state.client.set(
                        "scheduler_lock", scheduler_id, nx=True, ex=LOCK_TTL_SECONDS
                    )
                else:
                    lock_acquired = True

                if lock_acquired:
                    released = await engine.release_due_jobs()
                    if released:
                        logger.info("Released %s due job(s)", released)

                    requeued = await engine.requeue_expired_leases(settings.worker_lease_seconds)
                    if requeued:
                        logger.info("Requeued %s job(s) with expired leases", requeued)

                    expired_workers = await engine.heartbeat_expired_workers()
                    if expired_workers:
                        logger.info("Marked %s worker(s) inactive", expired_workers)

                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=POLL_SECONDS)
                except TimeoutError:
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - keep the scheduler alive
                logger.error("Scheduler error: %s", exc, exc_info=True)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=ERROR_BACKOFF_SECONDS)
                except TimeoutError:
                    continue
    finally:
        stop_event.set()
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        if state.available:
            try:
                await state.client.delete("scheduler_lock")
            except Exception as exc:  # noqa: BLE001 - shutdown must not raise
                logger.debug("Scheduler lock release failed: %s", type(exc).__name__)
        await state.client.aclose()
        logger.info("Scheduler shut down gracefully")


async def main() -> None:
    """Entrypoint used by ``python -m taskmesh.scheduler``."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (getattr(os, "SIGTERM", None), getattr(os, "SIGINT", None)):
        if sig is None:  # pragma: no cover - platform dependent
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError, ValueError):
            # Windows, or a non-main thread; the loop still exits via
            # cancellation, so this is not fatal.
            pass
    await run_scheduler(stop_event)


if __name__ == "__main__":
    asyncio.run(main())
