"""Job-type handlers executed by TaskMesh workers.

A handler receives the persisted payload and returns the result that the worker
stores on the job. Anything a handler raises is recorded through the engine's
existing failure/retry path.
"""

from __future__ import annotations

from typing import Any

from .csv_analysis import CSV_JOB_TYPE, analyze_csv
from .errors import JobInputError
from .json_validation import JSON_JOB_TYPE, validate_json
from .text_processing import TEXT_JOB_TYPE, process_text


class UnsupportedJobType(ValueError):
    """Raised when a worker leases a job type that has no handler."""


def _text_payload(payload: dict[str, Any] | None) -> str:
    text = (payload or {}).get("text")
    if not isinstance(text, str):
        raise JobInputError("payload.text must be a string")
    return text


def _content_payload(payload: dict[str, Any] | None) -> str:
    content = (payload or {}).get("content")
    if not isinstance(content, str):
        raise JobInputError("payload.content must be a string")
    return content


def execute_job(job_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Execute one job of ``job_type`` and return its result."""
    if job_type == TEXT_JOB_TYPE:
        return process_text(_text_payload(payload))
    if job_type == JSON_JOB_TYPE:
        return validate_json(_content_payload(payload))
    if job_type == CSV_JOB_TYPE:
        return analyze_csv(_content_payload(payload))

    raise UnsupportedJobType(f"no handler is registered for job type '{job_type}'")
