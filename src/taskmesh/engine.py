from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, OperationalError

from .api.dependencies import engine as db_engine
from .db.models import Job as OrmJob, Worker as OrmWorker, Event as OrmEvent
from .models import JobCreate, JobStatus, Metrics, WorkerHeartbeat, utc_now

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

logger = logging.getLogger(__name__)


def _safe_uuid(value: str) -> uuid.UUID | None:
    """Parse a UUID string, returning None if invalid."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


def _orm_to_dict(obj: Any) -> dict[str, Any]:
    """Convert an ORM instance to a plain dict.

    Must be called while the object is still attached to an open session,
    i.e. inside the `async with AsyncSession(...)` block that loaded it.
    """
    if obj is None:
        return {}
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class RateLimiter:
    """Redis-based sliding-window rate limiter."""
    def __init__(self, limit: int = 100, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds

    def _redis(self):
        """Expose the module-level redis_client (for test cleanup)."""
        return redis_client

    async def allow(self, key: str, now: datetime | None = None) -> bool:
        """Determine if an action is allowed under the sliding-window limit.

        Falls back to allowing the request when Redis is unavailable (e.g. tests).
        """
        current = now or utc_now()
        ts = current.timestamp()
        redis_key = f"ratelimit:{key}"
        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(redis_key, 0, ts - self.window)
                pipe.zcard(redis_key)
                pipe.zadd(redis_key, {str(ts) + "-" + str(uuid.uuid4()): ts})
                pipe.expire(redis_key, self.window)
                results = await pipe.execute()
            current_count = results[1]
            return current_count < self.limit
        except Exception:
            return True


class TaskMeshEngine:
    def __init__(self) -> None:
        self.rate_limiter = RateLimiter()
        # Detect if we're using SQLite (doesn't support FOR UPDATE SKIP LOCKED)
        self._is_sqlite = "sqlite" in (os.getenv("DATABASE_URL", "") or "")

    async def _emit(
        self,
        session: AsyncSession,
        event_type: str,
        job_id: str | None,
        tenant_id: str,
        message: str,
    ) -> None:
        event = OrmEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            job_id=str(uuid.UUID(job_id)) if job_id else None,
            tenant_id=tenant_id,
            message=message,
        )
        session.add(event)

        payload = {
            "id": str(event.id),
            "event_type": event_type,
            "job_id": job_id,
            "tenant_id": tenant_id,
            "message": message,
            "created_at": utc_now().isoformat(),
        }
        try:
            await redis_client.publish("taskmesh_logs", json.dumps(payload))
        except Exception:
            pass

    @staticmethod
    def _is_future(value: datetime | None) -> bool:
        if value is None:
            return False
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value > utc_now()

    # ------------------------------------------------------------------
    # All methods return plain dicts (or lists/Metrics), never ORM objects.
    # _orm_to_dict is called inside each session block before it closes.
    # ------------------------------------------------------------------

    async def create_job(self, request: JobCreate) -> dict[str, Any]:
        if not await self.rate_limiter.allow(f"tenant:{request.tenant_id}:create"):
            raise ValueError("rate_limit_exceeded")

        async with AsyncSession(db_engine) as session:
            async with session.begin():
                if request.idempotency_key:
                    stmt = select(OrmJob).where(
                        OrmJob.tenant_id == request.tenant_id,
                        OrmJob.idempotency_key == request.idempotency_key,
                    )
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    if existing:
                        # Refresh so all columns are loaded before session closes
                        await session.refresh(existing)
                        return _orm_to_dict(existing)

                status = (
                    JobStatus.SCHEDULED if self._is_future(request.execute_at) else JobStatus.PENDING
                )
                job_id = str(uuid.uuid4())
                job = OrmJob(
                    id=job_id,
                    job_type=request.job_type,
                    payload=request.payload,
                    tenant_id=request.tenant_id,
                    priority=request.priority,
                    status=status.value,
                    execute_at=request.execute_at,
                    max_retries=request.max_retries,
                    idempotency_key=request.idempotency_key,
                    history=[f"{utc_now().isoformat()} JobCreated"],
                )
                session.add(job)
                await self._emit(
                    session, "JobCreated", str(job.id), job.tenant_id, f"Job {job.id} accepted"
                )
                await session.flush()
                await session.refresh(job)
                # Convert to dict BEFORE session closes
                return _orm_to_dict(job)

    async def list_jobs(
        self,
        tenant_id: str | None = None,
        status_filter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        async with AsyncSession(db_engine) as session:
            stmt = select(OrmJob).order_by(OrmJob.priority.desc(), OrmJob.created_at.desc())
            if tenant_id:
                stmt = stmt.where(OrmJob.tenant_id == tenant_id)
            if status_filter:
                stmt = stmt.where(OrmJob.status == status_filter)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            # Convert inside the session while objects are still attached
            return [_orm_to_dict(j) for j in jobs]

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        async with AsyncSession(db_engine) as session:
            job = await session.get(OrmJob, job_id)
            if job is None:
                return None
            return _orm_to_dict(job)

    async def lease_next_job(self, worker_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        """Lease the next pending job for a worker.

        Uses FOR UPDATE SKIP LOCKED on PostgreSQL for safe concurrent access.
        Falls back to a simpler atomic UPDATE-based approach on SQLite (which doesn't
        support SKIP LOCKED).
        """
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                if self._is_sqlite:
                    # SQLite fallback: use a simpler approach without FOR UPDATE SKIP LOCKED
                    # First, find a pending job
                    stmt = select(OrmJob).where(OrmJob.status == JobStatus.PENDING.value)
                    if tenant_id:
                        stmt = stmt.where(OrmJob.tenant_id == tenant_id)
                    stmt = stmt.order_by(OrmJob.priority.desc(), OrmJob.created_at.asc()).limit(1)
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()
                    if not job:
                        return None

                    # Now atomically update it to RUNNING (if still pending)
                    update_stmt = (
                        update(OrmJob)
                        .where(
                            OrmJob.id == job.id,
                            OrmJob.status == JobStatus.PENDING.value,
                        )
                        .values(
                            status=JobStatus.RUNNING.value,
                            worker_id=worker_id,
                            started_at=utc_now(),
                        )
                    )
                    result = await session.execute(update_stmt)
                    if result.rowcount == 0:
                        # Another worker grabbed it — return None so caller retries
                        return None

                    # Re-fetch the updated job
                    job = await session.get(OrmJob, job.id)
                else:
                    stmt = select(OrmJob).where(OrmJob.status == JobStatus.PENDING.value)
                    if tenant_id:
                        stmt = stmt.where(OrmJob.tenant_id == tenant_id)
                    stmt = (
                        stmt.order_by(OrmJob.priority.desc(), OrmJob.created_at.asc())
                        .with_for_update(skip_locked=True)
                        .limit(1)
                    )
                    result = await session.execute(stmt)
                    job = result.scalar_one_or_none()
                    if not job:
                        return None

                    job.status = JobStatus.RUNNING.value
                    job.worker_id = worker_id
                    job.started_at = utc_now()

                job.history = job.history + [f"{utc_now().isoformat()} JobStarted by {worker_id}"]

                await self._emit(
                    session, "JobStarted", str(job.id), job.tenant_id, f"{worker_id} leased job {job.id}"
                )
                await session.flush()
                await session.refresh(job)
                return _orm_to_dict(job)

    async def complete_job(self, job_id: str) -> dict[str, Any]:
        uid = _safe_uuid(job_id)
        if not uid:
            raise KeyError(job_id)
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                if self._is_sqlite:
                    # SQLite: simpler update without FOR UPDATE
                    stmt = (
                        update(OrmJob)
                        .where(OrmJob.id == str(uid))
                        .values(
                            status=JobStatus.COMPLETED.value,
                            completed_at=utc_now(),
                        )
                    )
                    result = await session.execute(stmt)
                    if result.rowcount == 0:
                        raise KeyError(job_id)
                    job = await session.get(OrmJob, str(uid))
                else:
                    job = await session.get(OrmJob, str(uid), with_for_update=True)
                    if not job:
                        raise KeyError(job_id)

                    job.status = JobStatus.COMPLETED.value
                    job.completed_at = utc_now()

                job.history = job.history + [f"{utc_now().isoformat()} JobCompleted"]

                await self._emit(
                    session, "JobCompleted", str(job.id), job.tenant_id, f"Job {job.id} completed"
                )
                await session.flush()
                await session.refresh(job)
                return _orm_to_dict(job)

    async def fail_job(self, job_id: str, reason: str) -> dict[str, Any]:
        uid = _safe_uuid(job_id)
        if not uid:
            raise KeyError(job_id)
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                if self._is_sqlite:
                    job = await session.get(OrmJob, str(uid))
                    if not job:
                        raise KeyError(job_id)
                else:
                    job = await session.get(OrmJob, str(uid), with_for_update=True)
                    if not job:
                        raise KeyError(job_id)

                job.failure_reason = reason
                job.retry_count += 1

                if job.retry_count > job.max_retries:
                    job.status = JobStatus.DEAD_LETTER.value
                    job.completed_at = utc_now()
                    event_type = "JobDeadLettered"
                    message = f"Job {job.id} moved to DLQ after {job.retry_count} attempts"
                else:
                    job.status = JobStatus.SCHEDULED.value
                    backoff_seconds = min(2 ** job.retry_count, 300)
                    job.execute_at = utc_now() + timedelta(seconds=backoff_seconds)
                    event_type = "JobRetryScheduled"
                    message = f"Job {job.id} retry {job.retry_count} scheduled in {backoff_seconds}s"

                job.history = job.history + [f"{utc_now().isoformat()} {event_type}: {reason}"]
                await self._emit(session, event_type, str(job.id), job.tenant_id, message)
                await session.flush()
                await session.refresh(job)
                return _orm_to_dict(job)

    async def replay_dead_letter(self, job_id: str) -> dict[str, Any]:
        uid = _safe_uuid(job_id)
        if not uid:
            raise KeyError(job_id)
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                job = await session.get(OrmJob, str(uid))
                if not job:
                    raise KeyError(job_id)
                if job.status != JobStatus.DEAD_LETTER.value:
                    raise ValueError("job_not_in_dead_letter")

                job.status = JobStatus.PENDING.value
                job.retry_count = 0
                job.failure_reason = None
                job.execute_at = None
                job.completed_at = None
                job.history = job.history + [f"{utc_now().isoformat()} JobReplayed"]

                await self._emit(
                    session, "JobReplayed", str(job.id), job.tenant_id, f"Job {job.id} replayed from DLQ"
                )
                await session.flush()
                await session.refresh(job)
                return _orm_to_dict(job)

    async def heartbeat(self, request: WorkerHeartbeat) -> dict[str, Any]:
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                worker = await session.get(OrmWorker, request.worker_id)
                if not worker:
                    worker = OrmWorker(id=request.worker_id)
                    session.add(worker)

                worker.hostname = request.hostname
                worker.cpu_usage = request.cpu_usage
                worker.memory_usage = request.memory_usage
                worker.active_jobs = request.active_jobs
                worker.last_heartbeat = utc_now()
                worker.status = "active"

                await session.flush()
                await session.refresh(worker)
                return _orm_to_dict(worker)

    async def release_due_jobs(self) -> int:
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                stmt = (
                    update(OrmJob)
                    .where(
                        OrmJob.status == JobStatus.SCHEDULED.value,
                        OrmJob.execute_at <= utc_now(),
                    )
                    .values(status=JobStatus.PENDING.value)
                )
                result = await session.execute(stmt)
                return result.rowcount

    async def metrics(self) -> Metrics:
        async with AsyncSession(db_engine) as session:
            stmt = select(OrmJob.status, func.count(OrmJob.id)).group_by(OrmJob.status)
            result = await session.execute(stmt)
            counts = {
                status.value if isinstance(status, JobStatus) else status: count
                for status, count in result.all()
            }

            active_limit = utc_now() - timedelta(minutes=5)
            worker_stmt = select(func.count(OrmWorker.id)).where(
                OrmWorker.last_heartbeat >= active_limit
            )
            active_workers = (await session.execute(worker_stmt)).scalar() or 0

            retry_stmt = select(func.count(OrmJob.id)).where(OrmJob.retry_count > 0)
            retry_jobs = (await session.execute(retry_stmt)).scalar() or 0

            total_jobs = sum(counts.values()) or 1
            completed = counts.get(JobStatus.COMPLETED.value, 0)
            failedish = counts.get(JobStatus.FAILED.value, 0) + counts.get(JobStatus.DEAD_LETTER.value, 0)
            total_done = completed + failedish

            return Metrics(
                pending=counts.get(JobStatus.PENDING.value, 0),
                scheduled=counts.get(JobStatus.SCHEDULED.value, 0),
                running=counts.get(JobStatus.RUNNING.value, 0),
                completed=completed,
                failed=counts.get(JobStatus.FAILED.value, 0),
                dead_letter=counts.get(JobStatus.DEAD_LETTER.value, 0),
                active_workers=active_workers,
                throughput_per_minute=total_done,
                retry_rate=round(retry_jobs / total_jobs, 3),
            )

    async def lease_job_by_id(self, job_id: str, worker_id: str | None = None) -> dict[str, Any] | None:
        """Lease a specific job by ID (used by worker /jobs/{id}/lease endpoint)."""
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                job = await session.get(OrmJob, job_id)
                if not job or job.status not in (JobStatus.PENDING.value, JobStatus.SCHEDULED.value):
                    return None
                job.status = JobStatus.RUNNING.value
                job.worker_id = worker_id or "unknown"
                job.started_at = utc_now()
                job.history = job.history + [f"{utc_now().isoformat()} JobLeased"]
                await self._emit(
                    session, "JobLeased", str(job.id), job.tenant_id, f"Job {job.id} leased by {worker_id}"
                )
                await session.flush()
                await session.refresh(job)
                return _orm_to_dict(job)

    async def delete_job(self, job_id: str) -> None:
        """Delete a job by ID."""
        uid = _safe_uuid(job_id)
        if not uid:
            return
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                job = await session.get(OrmJob, str(uid))
                if job:
                    await session.delete(job)

    async def list_workers(self, active_only: bool = False) -> list[dict[str, Any]]:
        """List all workers, optionally filtering to active ones (heartbeat within 5 min)."""
        async with AsyncSession(db_engine) as session:
            stmt = select(OrmWorker).order_by(OrmWorker.last_heartbeat.desc())
            if active_only:
                active_limit = utc_now() - timedelta(minutes=5)
                stmt = stmt.where(OrmWorker.last_heartbeat >= active_limit)
            result = await session.execute(stmt)
            workers = result.scalars().all()
            return [_orm_to_dict(w) for w in workers]

    async def heartbeat_expired_workers(self, timeout_minutes: int = 1) -> int:
        """Mark workers as inactive if they haven't sent a heartbeat within timeout_minutes."""
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                inactive_limit = utc_now() - timedelta(minutes=timeout_minutes)
                stmt = (
                    update(OrmWorker)
                    .where(
                        OrmWorker.last_heartbeat < inactive_limit,
                        OrmWorker.status != "inactive",
                    )
                    .values(status="inactive")
                )
                result = await session.execute(stmt)
                return result.rowcount

    async def list_events(
        self,
        job_id: str | None = None,
        tenant_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List events with optional filtering."""
        async with AsyncSession(db_engine) as session:
            stmt = select(OrmEvent).order_by(OrmEvent.created_at.desc())
            if job_id:
                stmt = stmt.where(OrmEvent.job_id == job_id)
            if tenant_id:
                stmt = stmt.where(OrmEvent.tenant_id == tenant_id)
            if event_type:
                stmt = stmt.where(OrmEvent.event_type == event_type)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            events = result.scalars().all()
            return [_orm_to_dict(e) for e in events]

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a pending or scheduled job."""
        uid = _safe_uuid(job_id)
        if not uid:
            raise KeyError(job_id)
        async with AsyncSession(db_engine) as session:
            async with session.begin():
                job = await session.get(OrmJob, str(uid))
                if not job:
                    raise KeyError(job_id)
                if job.status not in (JobStatus.PENDING.value, JobStatus.SCHEDULED.value):
                    raise ValueError("Only pending or scheduled jobs can be cancelled")
                job.status = JobStatus.CANCELED.value
                job.history = job.history + [f"{utc_now().isoformat()} JobCancelled"]
                await self._emit(
                    session, "JobCancelled", str(job.id), job.tenant_id, f"Job {job.id} cancelled"
                )
                await session.flush()
                await session.refresh(job)
                return _orm_to_dict(job)

    async def analytics_time_series(self, hours: int = 24) -> list[dict[str, Any]]:
        """Return time-series data for analytics charts.
        
        Groups jobs by hour for the last N hours, broken down by status.
        Works with both PostgreSQL and SQLite.
        """
        from sqlalchemy import func as sa_func, extract, cast, Date
        
        since = utc_now() - timedelta(hours=hours)
        async with AsyncSession(db_engine) as session:
            # For simplicity, use the created_at field grouped by hour
            # This works cross-database
            stmt = (
                select(
                    OrmJob.status,
                    sa_func.count(OrmJob.id).label("count"),
                    OrmJob.created_at,
                )
                .where(OrmJob.created_at >= since)
                .group_by(OrmJob.status, OrmJob.created_at)
                .order_by(OrmJob.created_at.asc())
            )
            result = await session.execute(stmt)
            rows = result.all()
            
            # Aggregate into hourly buckets
            hourly: dict[str, dict[str, int]] = {}
            for row in rows:
                created = row.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                hour_key = created.strftime("%Y-%m-%dT%H:00:00")
                if hour_key not in hourly:
                    hourly[hour_key] = {
                        "hour": hour_key,
                        "created": 0,
                        "completed": 0,
                        "failed": 0,
                        "running": 0,
                        "pending": 0,
                        "dead_letter": 0,
                    }
                status = row.status
                count = row.count
                if status == JobStatus.COMPLETED.value:
                    hourly[hour_key]["completed"] += count
                elif status in (JobStatus.FAILED.value, JobStatus.DEAD_LETTER.value):
                    hourly[hour_key]["failed"] += count
                elif status == JobStatus.RUNNING.value:
                    hourly[hour_key]["running"] += count
                elif status == JobStatus.PENDING.value:
                    hourly[hour_key]["pending"] += count
                elif status == JobStatus.DEAD_LETTER.value:
                    hourly[hour_key]["dead_letter"] += count
                hourly[hour_key]["created"] += count
            
            return list(hourly.values())

    async def duplicate_job(self, job_id: str) -> dict[str, Any]:
        """Duplicate a job by creating a copy with a new ID."""
        uid = _safe_uuid(job_id)
        if not uid:
            raise KeyError(job_id)
        async with AsyncSession(db_engine) as session:
            job = await session.get(OrmJob, str(uid))
            if not job:
                raise KeyError(job_id)
            
            # Create a new job from the existing one
            from .models import JobCreate
            new_request = JobCreate(
                job_type=job.job_type,
                payload=job.payload,
                priority=job.priority,
                tenant_id=job.tenant_id,
                max_retries=job.max_retries,
            )
            # Note: we're outside the session for the old job now
        return await self.create_job(new_request)

    async def health_check_redis(self) -> bool:
        """Check if Redis is reachable. Returns False if not."""
        try:
            await redis_client.ping()
            return True
        except Exception:
            return False


engine = TaskMeshEngine()
