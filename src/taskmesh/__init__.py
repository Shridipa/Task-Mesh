# Centralized Base definition moved to taskmesh.db.base
from .db.base import Base  # noqa: F401

# Import models so SQLAlchemy registers them
from . import models  # noqa: F401,E402
