"""Structured logging for TaskMesh.

``LOG_FORMAT=text`` gives readable developer output; ``LOG_FORMAT=json`` emits
one JSON object per line for log collectors. Every record can carry the fields
the application adds through ``extra`` (job id, worker id, duration, request
id, …). Secrets are never logged: database URLs are passed through
:func:`taskmesh.config.redact_url` before they reach this module.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

from .config import get_settings

#: Request id of the HTTP request currently being handled (if any).
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

#: Fields copied from ``LogRecord.extra`` into JSON output.
STRUCTURED_FIELDS = (
    "service",
    "environment",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "job_id",
    "job_type",
    "worker_id",
    "scheduler_id",
    "jobs_handled",
    "status",
    "database",
)


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            request_id = request_id_var.get()
            if request_id:
                record.request_id = request_id
        return True


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Readable single-line output that still shows structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()} "
            f"{record.levelname:<8} {record.name}: {record.getMessage()}"
        )
        extra = {
            field: getattr(record, field)
            for field in STRUCTURED_FIELDS
            if getattr(record, field, None) is not None
        }
        if extra:
            base += " " + " ".join(f"{key}={value}" for key, value in extra.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(service: str = "taskmesh-api") -> None:
    """Install a single stdout handler with the configured format and level."""
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if settings.log_format == "json" else TextFormatter()
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Uvicorn installs its own handlers; route them through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured", extra={"service": service, "environment": settings.environment}
    )
