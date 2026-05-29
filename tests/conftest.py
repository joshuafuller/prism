"""Shared test fixtures: a fake subprocess Runner so engines never call a real model."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from prism.engines.base import CompletedProc


class FakeRunner:
    """Records each invocation and returns scripted CompletedProcs in order.

    The last scripted output is reused if called more times than outputs provided.
    Set ``raise_timeout`` to simulate a hung process.
    """

    def __init__(self, outputs: list[CompletedProc], *, raise_timeout: bool = False) -> None:
        self._outputs = outputs
        self._raise_timeout = raise_timeout
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        argv: list[str],
        stdin: str,
        *,
        inactivity_s: float = 0.0,
        overall_s: float = 0.0,
        heartbeat: object = None,
    ) -> CompletedProc:
        self.calls.append({"argv": argv, "stdin": stdin})
        if self._raise_timeout:
            raise TimeoutError("simulated timeout")
        return self._outputs[min(len(self.calls) - 1, len(self._outputs) - 1)]

    @property
    def last_argv(self) -> list[str]:
        return self.calls[-1]["argv"]  # type: ignore[return-value]

    @property
    def last_stdin(self) -> str:
        return self.calls[-1]["stdin"]  # type: ignore[return-value]


@pytest.fixture
def fake_runner() -> type[FakeRunner]:
    """Return the FakeRunner factory; call it with a list of CompletedProcs."""
    return FakeRunner


@pytest.fixture
def make_proc() -> Callable[..., CompletedProc]:
    """Factory for a CompletedProc with sensible defaults."""

    def _make(stdout: str = "", *, code: int = 0, stderr: str = "") -> CompletedProc:
        return CompletedProc(code, stdout, stderr)

    return _make


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """An initialized git repo on branch `main` with one base commit (a.py)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo / "a.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    return repo
