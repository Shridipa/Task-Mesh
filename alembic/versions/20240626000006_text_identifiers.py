"""Store identifiers as text and JSON payloads as jsonb

Revision ID: 20240626000006
Revises: 20240626000005
Create Date: 2026-11-19 00:00:06

The ORM models declare job/event identifiers as ``String`` because the rest of
the application handles them as plain strings (``str(uuid.uuid4())``). Earlier
migrations created those columns as PostgreSQL ``uuid`` instead, which made
asyncpg reject every insert with::

    column "id" is of type uuid but expression is of type character varying

This migration aligns the physical schema with the models: identifiers become
``VARCHAR`` (lossless, ``uuid::text``) and the JSON document columns become
``jsonb`` to match the ``JSON`` columns, which SQLAlchemy renders as ``JSONB``
on PostgreSQL.

Only PostgreSQL is affected; SQLite stores these values as TEXT already.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20240626000006"
down_revision = "20240626000005"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    # Foreign keys must go before the referenced column types can change.
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS fk_events_job_id")
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS events_job_id_fkey")

    op.execute("ALTER TABLE jobs ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE jobs ALTER COLUMN id TYPE VARCHAR USING id::text")

    op.execute("ALTER TABLE events ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE events ALTER COLUMN id TYPE VARCHAR USING id::text")
    op.execute("ALTER TABLE events ALTER COLUMN job_id TYPE VARCHAR USING job_id::text")

    op.create_foreign_key(
        "fk_events_job_id", "events", "jobs", ["job_id"], ["id"], ondelete="CASCADE"
    )

    # The ORM maps these columns as JSON, which SQLAlchemy stores as JSONB on
    # PostgreSQL; converting keeps autogenerate output clean.
    op.execute("ALTER TABLE jobs ALTER COLUMN payload TYPE JSONB USING payload::jsonb")


def downgrade() -> None:
    if not _is_postgres():
        return

    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS fk_events_job_id")
    op.execute("ALTER TABLE jobs ALTER COLUMN payload TYPE JSON USING payload::json")
    op.execute("ALTER TABLE events ALTER COLUMN job_id TYPE UUID USING job_id::uuid")
    op.execute("ALTER TABLE events ALTER COLUMN id TYPE UUID USING id::uuid")
    op.execute("ALTER TABLE jobs ALTER COLUMN id TYPE UUID USING id::uuid")
    op.create_foreign_key(
        "fk_events_job_id", "events", "jobs", ["job_id"], ["id"], ondelete="CASCADE"
    )
