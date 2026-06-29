"""Job service — delegates directly to TaskMeshEngine.

All job operations are handled by the PostgreSQL-backed engine.
This module exists to provide a clean import path for the API routes.
"""
from __future__ import annotations

from ...engine import engine as _engine

# Re-export the engine singleton
engine = _engine
