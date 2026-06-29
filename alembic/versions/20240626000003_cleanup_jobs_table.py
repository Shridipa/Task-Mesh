"""Cleanup jobs table — add missing columns, add performance index.

Revision ID: 20240626000003
Revises: 20240626000002
Create Date: 2024-06-26 00:00:03

NOTE: Migration 002 already renamed 'type' -> 'job_type' and dropped
'updated_at'. This migration only adds columns that 002 may have missed on
older branches and creates the composite index required for efficient querying.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20240626000003"
down_revision = "20240626000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the execute_at index for scheduler performance (idempotent via IF NOT EXISTS via raw SQL).
    # We use op.execute so it does not fail if the index already exists on replayed migrations.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status_priority "
        "ON jobs (tenant_id, status, priority DESC, created_at ASC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency "
        "ON jobs (tenant_id, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_idempotency")
    op.execute("DROP INDEX IF EXISTS idx_jobs_tenant_status_priority")
