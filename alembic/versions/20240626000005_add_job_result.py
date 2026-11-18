"""Add a nullable JSON result column to jobs

Revision ID: 20240626000005
Revises: 20240626000004
Create Date: 2024-06-26 00:00:05

Workers store the output of an executed job in ``jobs.result`` so the value
survives a page refresh and can be read back through the API.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision = "20240626000005"
down_revision = "20240626000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("result", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "result")
