"""Streaming runner: kills on inactivity (not wall-clock), heartbeats, generous cap.

Uses real, harmless subprocesses (sh/cat/sleep) — never an LLM.
"""

import pytest

from prism.engines.base import streaming_subprocess_runner


def test_captures_output_and_returncode() -> None:
    proc = streaming_subprocess_runner(
        ["sh", "-c", "printf hello"], "", inactivity_s=2.0, overall_s=5.0
    )
    assert proc.returncode == 0
    assert proc.stdout == "hello"


def test_feeds_stdin() -> None:
    proc = streaming_subprocess_runner(["cat"], "piped-in", inactivity_s=2.0, overall_s=5.0)
    assert proc.stdout == "piped-in"


def test_kills_on_inactivity() -> None:
    with pytest.raises(TimeoutError):
        streaming_subprocess_runner(["sh", "-c", "sleep 3"], "", inactivity_s=0.3, overall_s=10.0)


def test_does_not_kill_a_slow_but_active_process() -> None:
    # Emits every 0.1s for ~0.6s; an inactivity window of 0.4s must never trip, so it
    # runs to completion even though total runtime exceeds the inactivity window.
    proc = streaming_subprocess_runner(
        ["sh", "-c", "for i in 1 2 3 4 5 6; do echo $i; sleep 0.1; done"],
        "",
        inactivity_s=0.4,
        overall_s=10.0,
    )
    assert proc.returncode == 0
    assert proc.stdout.split() == ["1", "2", "3", "4", "5", "6"]


def test_kills_on_overall_cap_even_while_active() -> None:
    # Never goes inactive, but exceeds the generous overall backstop -> killed.
    with pytest.raises(TimeoutError):
        streaming_subprocess_runner(
            ["sh", "-c", "while true; do echo .; sleep 0.05; done"],
            "",
            inactivity_s=5.0,
            overall_s=0.4,
        )


def test_emits_heartbeat_while_quiet() -> None:
    beats: list[float] = []
    streaming_subprocess_runner(
        ["sh", "-c", "sleep 0.5"],
        "",
        inactivity_s=3.0,
        overall_s=5.0,
        heartbeat=beats.append,
        heartbeat_interval_s=0.1,
    )
    assert len(beats) >= 1
