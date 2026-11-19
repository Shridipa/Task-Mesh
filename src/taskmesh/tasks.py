"""Job-type handlers executed by TaskMesh workers."""
from __future__ import annotations
from typing import Any
from .text_processing import TEXT_JOB_TYPE, process_text
from .json_validation import JSON_JOB_TYPE, validate_json
from .csv_analysis import CSV_JOB_TYPE, analyze_csv
class UnsupportedJobType(ValueError):
    """Raised when a leased job type has no handler."""
def execute_job(job_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Dispatch persisted jobs to deterministic handlers."""
    data=payload or {}
    if job_type==TEXT_JOB_TYPE:
        text=data.get("text")
        if not isinstance(text,str): raise ValueError("payload.text must be a string")
        return process_text(text)
    if job_type==JSON_JOB_TYPE:
        raw=data.get("json_text")
        if not isinstance(raw,str): raise ValueError("payload.json_text must be a string")
        return validate_json(raw)
    if job_type==CSV_JOB_TYPE:
        raw=data.get("csv_text")
        if not isinstance(raw,str): raise ValueError("payload.csv_text must be a string")
        return analyze_csv(raw)
    raise UnsupportedJobType(f"no handler is registered for job type '{job_type}'")
