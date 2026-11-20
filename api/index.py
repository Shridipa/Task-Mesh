"""Vercel entrypoint for the TaskMesh FastAPI application.

Vercel's Python runtime loads the top-level ``app`` object from a recognised
entrypoint file. The application package lives in ``src/`` — the same layout the
Docker image installs — so the source directory is added to ``sys.path`` before
importing it. Nothing else is initialised here: routes, middleware, CORS,
authentication and lifespan all come from :mod:`taskmesh.api.main`, exactly as
they do under uvicorn.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from taskmesh.api.main import app  # noqa: E402,F401 - Vercel looks for `app`
