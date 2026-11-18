"""Job-type handlers executed by TaskMesh workers.

A handler receives the persisted payload and returns the result that the worker
stores on the job. Anything a handler raises is recorded through the engine's
existing failure/retry path.
"""

from __future__ import annotations

from typing import Any

from .text_processing import TEXT_JOB_TYPE, process_text


class UnsupportedJobType(ValueError):
    """Raised when a worker leases a job type that has no handler."""


def execute_job(job_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Execute one job of ``job_type`` and return its result."""
    if job_type == TEXT_JOB_TYPE:
        text = (payload or {}).get("text")
        if not isinstance(text, str):
            raise ValueError("payload.text must be a string")
        return process_text(text)

    raise UnsupportedJobType(f"no handler is registered for job type '{job_type}'")
