from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELED = "canceled"


class Role(StrEnum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"

class JobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=0, le=9)
    tenant_id: str = Field(default="default", min_length=1, max_length=80)
    execute_at: datetime | None = None
    max_retries: int = Field(default=5, ge=0, le=20)
    idempotency_key: str | None = Field(default=None, max_length=120)

class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: str
    payload: dict[str, Any]
    tenant_id: str
    priority: int
    status: JobStatus = JobStatus.PENDING
    retry_count: int = 0
    max_retries: int = 5
    failure_reason: str | None = None
    idempotency_key: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    execute_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker_id: str | None = None
    history: list[str] = Field(default_factory=list)


class WorkerHeartbeat(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    worker_id: str
    hostname: str
    cpu_usage: float = Field(ge=0, le=100)
    memory_usage: float = Field(ge=0, le=100)
    active_jobs: int = Field(default=0, ge=0)


class Worker(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    hostname: str
    cpu_usage: float
    memory_usage: float
    active_jobs: int
    status: str = "active"
    last_heartbeat: datetime = Field(default_factory=utc_now)


class Event(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    job_id: str | None = None
    tenant_id: str = "default"
    message: str
    created_at: datetime = Field(default_factory=utc_now)


class Metrics(BaseModel):
    pending: int
    scheduled: int
    running: int
    completed: int
    failed: int
    dead_letter: int
    active_workers: int
    throughput_per_minute: int
    retry_rate: float

