"""SQLAlchemy ORM models for TaskMesh.

These models are the source of truth for the schema. They are kept in exact
agreement with the Alembic migration history (``alembic check`` reports no
differences on PostgreSQL) so a database can be created either by running
migrations in production or by ``create_all`` in development and tests.

Types are chosen so both backends agree: identifiers are strings (the
application uses ``str(uuid.uuid4())``), statuses are short strings that mirror
:class:`taskmesh.models.JobStatus`, and JSON documents use ``JSON`` with a
``JSONB`` variant on PostgreSQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..models import JobStatus
from .base import Base

#: JSON that becomes ``jsonb`` on PostgreSQL and ``TEXT`` on SQLite.
JSONDocument = JSON().with_variant(JSONB(), "postgresql")


def utc_now() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "idx_jobs_tenant_status_priority",
            "tenant_id",
            "status",
            text("priority DESC"),
            "created_at",
        ),
        Index(
            "idx_jobs_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    job_type: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONDocument, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONDocument, nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, default="default")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=JobStatus.PENDING.value
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    execute_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Worker ids are a soft reference: a worker may lease a job before its
    # heartbeat row exists and rows are removed when a worker retires.
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    history: Mapped[List[str]] = mapped_column(JSONDocument, nullable=False, default=list)


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    active_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True
    )
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, default="default")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
