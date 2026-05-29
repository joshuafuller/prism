"""Characterization tests for the real subprocess_runner (the production CLI path).

Uses harmless real commands (cat/sh/sleep) — never an LLM — to cover the default
runner: stdin delivery, return-code capture, and timeout -> TimeoutError mapping.
"""

import pytest

from prism.engines.base import subprocess_runner


def test_runner_feeds_stdin_and_captures_stdout() -> None:
    proc = subprocess_runner(["cat"], "hello-stdin", 10.0)
    assert proc.returncode == 0
    assert proc.stdout == "hello-stdin"


def test_runner_reports_nonzero_returncode_and_stderr() -> None:
    proc = subprocess_runner(["sh", "-c", "echo oops >&2; exit 3"], "", 10.0)
    assert proc.returncode == 3
    assert "oops" in proc.stderr


def test_runner_maps_timeout_to_timeouterror() -> None:
    with pytest.raises(TimeoutError):
        subprocess_runner(["sleep", "5"], "", 0.2)
