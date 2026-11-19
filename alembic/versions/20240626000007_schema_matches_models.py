"""Make the remaining schema details match the ORM models

Revision ID: 20240626000007
Revises: 20240626000006
Create Date: 2026-11-19 00:00:07

Four leftovers from the initial schema are cleaned up so that ``alembic check``
reports no differences between the database and ``src/taskmesh/db/models.py``:

1. ``metrics`` is a legacy table that no code reads or writes.
2. ``events.job_id`` must be nullable: engine events are not always tied to a job.
3. ``jobs.created_at`` / ``events.created_at`` are always populated (server
   default) and are non-nullable in the models.
4. The unique *constraint* on ``(tenant_id, idempotency_key)`` duplicates the
   partial unique index the models declare.
5. ``jobs.worker_id`` no longer has a foreign key: a worker can lease a job
   before its heartbeat row exists, and worker rows are ephemeral.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20240626000007"
down_revision = "20240626000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS metrics")
    op.execute("ALTER TABLE events ALTER COLUMN job_id DROP NOT NULL")
    op.execute("UPDATE jobs SET created_at = now() WHERE created_at IS NULL")
    op.execute("ALTER TABLE jobs ALTER COLUMN created_at SET NOT NULL")
    op.execute("UPDATE events SET created_at = now() WHERE created_at IS NULL")
    op.execute("ALTER TABLE events ALTER COLUMN created_at SET NOT NULL")
    op.execute(
        "ALTER TABLE jobs DROP CONSTRAINT IF EXISTS uq_jobs_tenant_idempotency"
    )
    op.execute("ALTER TABLE jobs DROP CONSTRAINT IF EXISTS fk_jobs_worker_id")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT fk_jobs_worker_id "
        "FOREIGN KEY (worker_id) REFERENCES workers (id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE jobs ADD CONSTRAINT uq_jobs_tenant_idempotency "
        "UNIQUE (tenant_id, idempotency_key)"
    )
    op.execute("ALTER TABLE events ALTER COLUMN created_at DROP NOT NULL")
    op.execute("ALTER TABLE jobs ALTER COLUMN created_at DROP NOT NULL")
    op.execute("ALTER TABLE events ALTER COLUMN job_id SET NOT NULL")
    op.execute(
        "CREATE TABLE IF NOT EXISTS metrics ("
        "id SERIAL PRIMARY KEY, "
        "key VARCHAR(255) NOT NULL, "
        "value DOUBLE PRECISION NOT NULL, "
        "recorded_at TIMESTAMP DEFAULT now())"
    )
