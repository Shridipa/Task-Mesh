"""Errors shared by job handlers, the engine and the worker.

``JobInputError`` marks a deterministic problem with the submitted payload.
Retrying such a job would produce the same failure, so the worker records it as
a permanent failure instead of scheduling retries.

``JobOwnershipError`` marks a lease violation: the worker tried to finish a job
it no longer holds (for example after the scheduler requeued an expired lease).
"""

from __future__ import annotations


class JobInputError(ValueError):
    """Raised when a payload is invalid and retrying cannot help."""


class JobOwnershipError(RuntimeError):
    """Raised when a worker tries to finish a job it does not own."""
