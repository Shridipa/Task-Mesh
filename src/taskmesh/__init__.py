# Centralized Base definition moved to taskmesh.db.base
# Import models so SQLAlchemy registers them
from . import models  # noqa: F401
from .db.base import Base  # noqa: F401
