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
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


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


# A Runner runs argv with the given stdin and timeout, returning a CompletedProc.
# It must raise TimeoutError when the timeout elapses. Injectable for testing.
Runner = Callable[[list[str], str, float], CompletedProc]


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


def subprocess_runner(argv: list[str], stdin: str, timeout: float) -> CompletedProc:
    """Default Runner: run a real subprocess, feeding ``stdin`` to its stdin."""
    try:
        proc = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(str(exc)) from exc
    return CompletedProc(proc.returncode, proc.stdout, proc.stderr)


_AUTH_MARKERS = ("401", "403", "unauthorized", "invalid api key", "authentication")
_RETRYABLE_MARKERS = ("429", "503", "overloaded", "rate limit", "too many requests")


class Engine(ABC):
    """Base engine: shared invoke/parse/retry/error-classification logic."""

    name: str = "engine"

    def __init__(self, runner: Runner | None = None, *, timeout_s: float = 300.0) -> None:
        self._runner: Runner = runner or subprocess_runner
        self._timeout_s = timeout_s

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
            proc = self._runner(argv, prompt, self._timeout_s)
        except TimeoutError as exc:
            raise EngineTimeout(f"{self.name} timed out after {self._timeout_s}s") from exc
        self._raise_for_status(proc)
        return self._parse(proc.stdout)

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
