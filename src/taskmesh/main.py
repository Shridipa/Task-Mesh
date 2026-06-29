"""Compatibility wrapper for legacy imports.

The original codebase exposed a FastAPI app via ``taskmesh.main``. After refactoring
into the layered ``taskmesh.api`` package we keep this thin wrapper so existing
imports (including the test suite) continue to work without modification.
"""

from .api.main import app  # re-export the FastAPI application
