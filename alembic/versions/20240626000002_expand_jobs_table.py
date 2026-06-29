"""Expand jobs table

Revision ID: 20240626000002
Revises: 20240626000001
Create Date: 2024-06-26 00:00:02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240626000002"
down_revision = "20240626000001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Rename column "type" to "job_type"
    op.alter_column("jobs", "type", new_column_name="job_type")
    # Drop the unused updated_at column
    op.drop_column("jobs", "updated_at")
    # Add new columns
    op.add_column("jobs", sa.Column("tenant_id", sa.String(length=80), nullable=False, server_default="default"))
    op.add_column("jobs", sa.Column("priority", sa.Integer, nullable=False, server_default="5"))
    op.add_column("jobs", sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("max_retries", sa.Integer, nullable=False, server_default="5"))
    op.add_column("jobs", sa.Column("failure_reason", sa.Text, nullable=True))
    op.add_column("jobs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("execute_at", sa.DateTime, nullable=True))
    op.add_column("jobs", sa.Column("started_at", sa.DateTime, nullable=True))
    op.add_column("jobs", sa.Column("completed_at", sa.DateTime, nullable=True))
    op.add_column("jobs", sa.Column("worker_id", sa.Integer, nullable=True))
    # Add foreign key constraint for worker_id
    op.create_foreign_key(
        "fk_jobs_worker_id", "jobs", "workers", ["worker_id"], ["id"], ondelete="SET NULL"
    )

def downgrade() -> None:
    # Revert foreign key
    op.drop_constraint("fk_jobs_worker_id", "jobs", type_="foreignkey")
    # Remove added columns
    op.drop_column("jobs", "worker_id")
    op.drop_column("jobs", "completed_at")
    op.drop_column("jobs", "started_at")
    op.drop_column("jobs", "execute_at")
    op.drop_column("jobs", "idempotency_key")
    op.drop_column("jobs", "failure_reason")
    op.drop_column("jobs", "max_retries")
    op.drop_column("jobs", "retry_count")
    op.drop_column("jobs", "priority")
    op.drop_column("jobs", "tenant_id")
    # Add back updated_at column (as nullable for downgrade safety)
    op.add_column("jobs", sa.Column("updated_at", sa.DateTime, nullable=True))
    # Rename job_type back to type
    op.alter_column("jobs", "job_type", new_column_name="type")
