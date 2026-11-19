"""Liveness files for long-running background loops.

The API exposes ``/health`` and ``/ready`` for containers to probe, but the
worker and scheduler have no HTTP surface. They touch a file on every loop
iteration instead; container health checks compare that file's mtime with the
expected poll interval. An idle worker is healthy, so the threshold is generous.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def touch_liveness(path: str | None) -> None:
    """Record that the calling loop is alive.

    Best effort: a failure to write the file must never stop the loop, so it is
    logged at debug level only.
    """
    if not path:
        return
    try:
        Path(path).touch(exist_ok=True)
    except OSError as exc:
        logger.debug("Could not update liveness file %s: %s", path, exc)


def main() -> int:  # pragma: no cover - used as ``python -m taskmesh.liveness``
    """Container health probe: ``python -m taskmesh.liveness /tmp/worker-alive 90``."""
    import sys

    if len(sys.argv) != 3:
        print("usage: python -m taskmesh.liveness <path> <max_age_seconds>", file=sys.stderr)
        return 2
    path, max_age = sys.argv[1], int(sys.argv[2])
    if os.path.exists(path) and time_since(path) <= max_age:
        return 0
    return 1


def time_since(path: str) -> float:
    """Seconds since the file was last modified (``inf`` when missing)."""
    import time

    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return float("inf")


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
