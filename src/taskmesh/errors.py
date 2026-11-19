"""Errors shared by job handlers and the worker.

``JobInputError`` marks a deterministic problem with the submitted payload.
Retrying such a job would produce the same failure, so the worker records it as
a permanent failure instead of scheduling retries.
"""

from __future__ import annotations


class JobInputError(ValueError):
    """Raised when a payload is invalid and retrying cannot help."""
