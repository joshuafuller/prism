"""The Engine abstraction: the single chokepoint for all LLM access.

Every reviewer and the coordinator reach a model only through an ``Engine``. Concrete
engines drive subscription CLIs (``claude``, ``codex``) or API SDKs, but the base class
owns the shared behavior so it is implemented and tested once (DRY):

- the prompt is delivered on **stdin**, never argv (avoids ARG_MAX on large diffs);
- one retry on a truncated (``length``) response;
- timeouts become ``EngineTimeout``;
- non-zero exits are classified into retryable vs. non-retryable errors.

Done-detection is trivial here because CLI invocations are one-shot: the subprocess
exits when finished (see ADR-0007). Tests inject a fake ``Runner`` so no real model is
ever called.
"""

from __future__ import annotations

import subprocess
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import IO, Protocol


class Effort(StrEnum):
    """Reasoning-effort knob, mapped per-engine to its CLI/SDK equivalent (ADR-0006)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


@dataclass(frozen=True, slots=True)
class ParsedResult:
    """The normalized result of one engine invocation."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CompletedProc:
    """Outcome of running a subprocess: what a ``Runner`` returns."""

    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    """Runs argv with stdin and returns a CompletedProc; raises TimeoutError on a limit.

    Injectable for testing. The production implementation is streaming_subprocess_runner.
    """

    def __call__(
        self,
        argv: list[str],
        stdin: str,
        *,
        inactivity_s: float,
        overall_s: float,
        heartbeat: Callable[[float], None] | None = None,
    ) -> CompletedProc: ...


def merge_usage(container: object, tokens_in: int, tokens_out: int) -> tuple[int, int]:
    """Return updated token counts from a ``usage`` block inside ``container``.

    Tolerant of missing/null/non-dict containers and usage blocks (real CLI output
    varies), returning the inputs unchanged when usage isn't present. Shared by the
    CLI engines so token parsing lives in one place (DRY).
    """
    if isinstance(container, dict):
        usage = container.get("usage")
        if isinstance(usage, dict):
            return usage.get("input_tokens", tokens_in), usage.get("output_tokens", tokens_out)
    return tokens_in, tokens_out


class EngineError(Exception):
    """Base class for engine failures."""


class EngineTimeout(EngineError):
    """The invocation exceeded its timeout."""


class EngineAuthError(EngineError):
    """Authentication failed. A different model will NOT fix this -> no failback."""


class EngineRetryable(EngineError):
    """Transient/overload error (e.g. 429/503) -> a failback/retry may help."""


def streaming_subprocess_runner(
    argv: list[str],
    stdin: str,
    *,
    inactivity_s: float,
    overall_s: float,
    heartbeat: Callable[[float], None] | None = None,
    heartbeat_interval_s: float = 30.0,
    poll_s: float = 0.05,
) -> CompletedProc:
    """Run a subprocess, streaming its output to track liveness.

    Kills the process when it produces **no output for ``inactivity_s``** (it has hung or
    crashed) rather than on a blunt wall-clock — so a model that is slowly but actively
    streaming is never killed for being slow. ``overall_s`` is a generous backstop cap.
    ``heartbeat(quiet_seconds)`` is called every ``heartbeat_interval_s`` while waiting,
    so a long-but-alive run is visibly working. Raises ``TimeoutError`` on either limit.
    """
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    out: list[str] = []
    err: list[str] = []
    last_activity = [time.monotonic()]
    lock = threading.Lock()

    def pump(stream: IO[str], sink: list[str]) -> None:
        for line in stream:
            with lock:
                sink.append(line)
                last_activity[0] = time.monotonic()

    threads: list[threading.Thread] = []
    for stream, sink in ((proc.stdout, out), (proc.stderr, err)):
        if stream is not None:
            t = threading.Thread(target=pump, args=(stream, sink), daemon=True)
            t.start()
            threads.append(t)

    if proc.stdin is not None:
        try:
            proc.stdin.write(stdin)
        finally:
            proc.stdin.close()

    start = time.monotonic()
    last_beat = start
    while proc.poll() is None:
        now = time.monotonic()
        with lock:
            quiet = now - last_activity[0]
        if quiet > inactivity_s:
            proc.kill()
            raise TimeoutError(f"no output for {inactivity_s:.0f}s (inactivity)")
        if now - start > overall_s:
            proc.kill()
            raise TimeoutError(f"exceeded overall cap of {overall_s:.0f}s")
        if heartbeat is not None and now - last_beat >= heartbeat_interval_s:
            heartbeat(quiet)
            last_beat = now
        time.sleep(poll_s)

    for t in threads:
        t.join(timeout=2.0)
    with lock:
        return CompletedProc(proc.returncode or 0, "".join(out), "".join(err))


_AUTH_MARKERS = ("401", "403", "unauthorized", "invalid api key", "authentication")
_RETRYABLE_MARKERS = ("429", "503", "overloaded", "rate limit", "too many requests")


class Engine(ABC):
    """Base engine: shared invoke/parse/retry/error-classification logic."""

    name: str = "engine"

    def __init__(
        self,
        runner: Runner | None = None,
        *,
        inactivity_s: float = 120.0,
        overall_s: float = 1500.0,
        heartbeat: Callable[[float], None] | None = None,
    ) -> None:
        self._runner: Runner = runner or streaming_subprocess_runner
        self._inactivity_s = inactivity_s
        self._overall_s = overall_s
        self._heartbeat = heartbeat
        # Cumulative token usage across all run() calls on this engine (for telemetry).
        self.tokens_in = 0
        self.tokens_out = 0

    @abstractmethod
    def _build_argv(self, effort: Effort, model: str | None) -> list[str]:
        """Build the command line (without the prompt; the prompt goes on stdin)."""

    @abstractmethod
    def _parse(self, stdout: str) -> ParsedResult:
        """Parse the CLI/SDK output into a ParsedResult."""

    def run(
        self,
        prompt: str,
        *,
        effort: Effort = Effort.MEDIUM,
        model: str | None = None,
    ) -> ParsedResult:
        """Invoke the model with ``prompt``, retrying once if it was truncated."""
        result = self._invoke_once(prompt, effort, model)
        if result.finish_reason == "length":
            result = self._invoke_once(prompt, effort, model)
        return result

    def _invoke_once(self, prompt: str, effort: Effort, model: str | None) -> ParsedResult:
        argv = self._build_argv(effort, model)
        try:
            proc = self._runner(
                argv,
                prompt,
                inactivity_s=self._inactivity_s,
                overall_s=self._overall_s,
                heartbeat=self._heartbeat,
            )
        except TimeoutError as exc:
            raise EngineTimeout(f"{self.name} timed out (inactivity/overall limit)") from exc
        self._raise_for_status(proc)
        result = self._parse(proc.stdout)
        self.tokens_in += result.tokens_in
        self.tokens_out += result.tokens_out
        return result

    def _raise_for_status(self, proc: CompletedProc) -> None:
        if proc.returncode == 0:
            return
        err = (proc.stderr or "").lower()
        detail = proc.stderr.strip() or f"exit code {proc.returncode}"
        if any(marker in err for marker in _AUTH_MARKERS):
            raise EngineAuthError(f"{self.name}: {detail}")
        if any(marker in err for marker in _RETRYABLE_MARKERS):
            raise EngineRetryable(f"{self.name}: {detail}")
        raise EngineError(f"{self.name}: {detail}")
