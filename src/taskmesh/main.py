"""Compatibility wrapper for legacy imports.

Provides the FastAPI ``app`` instance expected at ``taskmesh.main``.
"""

from .api.main import app  # re-export FastAPI application for backward compatibility
