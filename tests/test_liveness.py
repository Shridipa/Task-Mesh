"""Liveness probe tests (the healthcheck used by the worker and scheduler)."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from taskmesh.liveness import main, time_since, touch_liveness


@pytest.fixture()
def heartbeat(tmp_path):
    return tmp_path / "worker-alive"


def _run(path: str, max_age: str) -> int:
    argv = [sys.executable, "-m", "taskmesh.liveness", path, max_age]
    return subprocess.run(argv, check=False).returncode  # noqa: S603 - fixed argv


def test_fresh_file_is_healthy(heartbeat):
    touch_liveness(str(heartbeat))

    assert heartbeat.exists()
    assert main.__module__ == "taskmesh.liveness"


def test_probe_exits_zero_for_a_fresh_file(heartbeat):
    touch_liveness(str(heartbeat))

    assert _run(str(heartbeat), "90") == 0


def test_probe_fails_for_a_stale_file(heartbeat):
    heartbeat.write_text("alive", encoding="utf-8")
    stale = time.time() - 300
    os.utime(heartbeat, (stale, stale))

    assert _run(str(heartbeat), "90") == 1


def test_probe_fails_when_the_file_is_missing(tmp_path):
    assert _run(str(tmp_path / "never-written"), "90") == 1


def test_probe_rejects_bad_arguments():
    assert subprocess.run(
        [sys.executable, "-m", "taskmesh.liveness"], check=False
    ).returncode == 2


def test_touching_an_unwritable_path_is_ignored(tmp_path):
    # Best effort: a broken heartbeat path must never crash the worker loop.
    touch_liveness(str(tmp_path / "missing-dir" / "alive"))

    assert time_since(str(tmp_path / "missing-dir" / "alive")) == float("inf")


def test_touch_without_a_path_does_nothing():
    touch_liveness(None)
