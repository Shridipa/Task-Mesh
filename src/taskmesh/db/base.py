"""Database base module containing the single SQLAlchemy DeclarativeBase.
This module is imported by all ORM model definitions.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models.
    Used by Alembic for migrations and by the application for metadata.
    """

    pass
