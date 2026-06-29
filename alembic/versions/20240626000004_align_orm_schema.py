"""Align schema with ORM models v2

Revision ID: 20240626000004
Revises: 20240626000003
Create Date: 2024-06-26 00:00:04

This migration brings the database schema into alignment with the ORM models
defined in src/taskmesh/db/models.py:

1. Convert jobs.id from INTEGER to UUID
2. Convert events.id from INTEGER to UUID
3. Add jobs.history JSONB column
4. Add missing Worker columns (hostname, cpu_usage, memory_usage, active_jobs, status)
5. Change workers.id from INTEGER to TEXT (worker_id is a string hostname)
6. Convert all DateTime columns to TIMESTAMPTZ (timezone-aware)
7. Add unique constraint on (tenant_id, idempotency_key) for jobs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "20240626000004"
down_revision = "20240626000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Workers table: migrate from INTEGER PK to TEXT (string worker_id)
    # and add missing operational columns
    # -------------------------------------------------------------------------
    # Drop old FK from jobs before altering workers PK
    op.drop_constraint("fk_jobs_worker_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "worker_id")

    # Recreate workers with proper schema
    op.drop_table("workers")
    op.create_table(
        "workers",
        sa.Column("id", sa.String(255), primary_key=True, index=True),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("cpu_usage", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("memory_usage", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("active_jobs", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # -------------------------------------------------------------------------
    # Jobs table: convert id to UUID, add history, re-add worker_id as TEXT FK
    # -------------------------------------------------------------------------
    # Rename old integer PK (PostgreSQL requires a workaround)
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS events_job_id_fkey")
    op.execute("ALTER TABLE jobs ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE jobs ALTER COLUMN id TYPE UUID USING gen_random_uuid()")
    op.execute("ALTER TABLE jobs ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.execute("ALTER TABLE events ALTER COLUMN job_id TYPE UUID USING NULL")

    # Add history column
    op.add_column("jobs", sa.Column("history", JSONB, nullable=False, server_default="[]"))

    # Re-add worker_id as TEXT (string worker id)
    op.add_column("jobs", sa.Column("worker_id", sa.String(255), nullable=True))
    op.create_foreign_key(
        "fk_jobs_worker_id", "jobs", "workers", ["worker_id"], ["id"], ondelete="SET NULL"
    )

    # Fix timezone on datetime columns
    for col in ("created_at", "execute_at", "started_at", "completed_at"):
        op.execute(
            f"ALTER TABLE jobs ALTER COLUMN {col} TYPE TIMESTAMPTZ USING {col} AT TIME ZONE 'UTC'"
        )

    # -------------------------------------------------------------------------
    # Events table: convert id to UUID, fix FK, add missing columns
    # -------------------------------------------------------------------------
    op.execute("ALTER TABLE events ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE events ALTER COLUMN id TYPE UUID USING gen_random_uuid()")
    op.execute("ALTER TABLE events ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.add_column(
        "events", sa.Column("tenant_id", sa.String(80), nullable=False, server_default="default")
    )
    op.add_column("events", sa.Column("message", sa.Text, nullable=False, server_default=""))
    op.execute(
        "ALTER TABLE events ALTER COLUMN timestamp TYPE TIMESTAMPTZ USING timestamp AT TIME ZONE 'UTC'"
    )
    op.alter_column("events", "timestamp", new_column_name="created_at")
    # Re-add FK after id type change
    op.create_foreign_key(
        "fk_events_job_id", "events", "jobs", ["job_id"], ["id"], ondelete="CASCADE"
    )

    # -------------------------------------------------------------------------
    # Unique constraint for idempotency
    # -------------------------------------------------------------------------
    op.create_unique_constraint(
        "uq_jobs_tenant_idempotency", "jobs", ["tenant_id", "idempotency_key"]
    )

    # Fix workers last_heartbeat timezone
    op.execute(
        "ALTER TABLE workers ALTER COLUMN last_heartbeat TYPE TIMESTAMPTZ USING last_heartbeat AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    # Reverting UUID → INTEGER is destructive.
    # We drop the UUID columns and recreate them as SERIAL (integer)
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS events_job_id_fkey")
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS fk_events_job_id")
    op.execute("ALTER TABLE events DROP COLUMN id")
    op.execute("ALTER TABLE events ADD COLUMN id SERIAL PRIMARY KEY")
    op.execute("ALTER TABLE events DROP COLUMN job_id")
    op.execute("ALTER TABLE events ADD COLUMN job_id INTEGER")

    op.execute("ALTER TABLE jobs DROP COLUMN id CASCADE")
    op.execute("ALTER TABLE jobs ADD COLUMN id SERIAL PRIMARY KEY")

    op.create_foreign_key(
        "events_job_id_fkey", "events", "jobs", ["job_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_column("jobs", "history")

    op.drop_constraint("fk_jobs_worker_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "worker_id")
    op.add_column("jobs", sa.Column("worker_id", sa.Integer, nullable=True))

    op.drop_table("workers")
    op.create_table(
        "workers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("last_heartbeat", sa.DateTime, nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_worker_id", "jobs", "workers", ["worker_id"], ["id"], ondelete="SET NULL"
    )

    for col in ("created_at", "execute_at", "started_at", "completed_at"):
        op.execute(
            f"ALTER TABLE jobs ALTER COLUMN {col} TYPE TIMESTAMP WITHOUT TIME ZONE USING {col} AT TIME ZONE 'UTC'"
        )

    op.drop_column("events", "tenant_id")
    op.drop_column("events", "message")
    op.execute(
        "ALTER TABLE events ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE USING created_at AT TIME ZONE 'UTC'"
    )
    op.alter_column("events", "created_at", new_column_name="timestamp")

    op.drop_constraint("uq_jobs_tenant_idempotency", "jobs", type_="unique")
