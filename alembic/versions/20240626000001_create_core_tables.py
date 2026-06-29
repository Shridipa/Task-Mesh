"""Create core tables

Revision ID: 20240626000001
Revises: None
Create Date: 2024-06-26 00:00:01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20240626000001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("type", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), onupdate=sa.text("now()")),
    )
    op.create_table(
        "workers",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime, nullable=True),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.text("now()")),
    )

def downgrade() -> None:
    op.drop_table("metrics")
    op.drop_table("events")
    op.drop_table("workers")
    op.drop_table("jobs")
