import json

import pytest

from prism.engines.base import (
    CompletedProc,
    Effort,
    Engine,
    EngineAuthError,
    EngineRetryable,
    EngineTimeout,
    ParsedResult,
)


class DummyEngine(Engine):
    """Minimal concrete engine for testing the base template behavior."""

    name = "dummy"

    def _build_argv(self, effort: Effort, model: str | None) -> list[str]:
        return ["dummy-cli", "--effort", str(effort)]

    def _parse(self, stdout: str) -> ParsedResult:
        data = json.loads(stdout)
        return ParsedResult(
            text=data["text"],
            tokens_in=data.get("in", 0),
            tokens_out=data.get("out", 0),
            finish_reason=data.get("finish"),
        )


class Recorder:
    """Fake runner: records each call, returns scripted CompletedProcs in order."""

    def __init__(self, outputs: list[CompletedProc], *, raise_timeout: bool = False) -> None:
        self._outputs = outputs
        self._raise_timeout = raise_timeout
        self.calls: list[dict[str, object]] = []

    def __call__(self, argv: list[str], stdin: str, timeout: float) -> CompletedProc:
        self.calls.append({"argv": argv, "stdin": stdin, "timeout": timeout})
        if self._raise_timeout:
            raise TimeoutError("simulated timeout")
        return self._outputs[min(len(self.calls) - 1, len(self._outputs) - 1)]


def _ok(text: str = "hi", finish: str = "stop", tin: int = 5, tout: int = 3) -> CompletedProc:
    payload = json.dumps({"text": text, "in": tin, "out": tout, "finish": finish})
    return CompletedProc(0, payload, "")


def test_prompt_goes_to_stdin_not_argv() -> None:
    r = Recorder([_ok()])
    DummyEngine(runner=r).run("HELLO-PROMPT", effort=Effort.LOW)
    assert "HELLO-PROMPT" not in " ".join(r.calls[0]["argv"])  # type: ignore[arg-type]
    assert r.calls[0]["stdin"] == "HELLO-PROMPT"


def test_parses_text_and_token_usage() -> None:
    r = Recorder([_ok(text="reviewed", tin=10, tout=20)])
    res = DummyEngine(runner=r).run("p")
    assert res.text == "reviewed"
    assert res.tokens_in == 10
    assert res.tokens_out == 20


def test_truncation_retries_once_then_returns_full() -> None:
    r = Recorder([_ok(text="cut", finish="length"), _ok(text="full", finish="stop")])
    res = DummyEngine(runner=r).run("p")
    assert len(r.calls) == 2
    assert res.text == "full"
    assert res.finish_reason == "stop"


def test_timeout_raises_engine_timeout() -> None:
    r = Recorder([], raise_timeout=True)
    with pytest.raises(EngineTimeout):
        DummyEngine(runner=r).run("p")


def test_auth_error_is_not_retryable() -> None:
    r = Recorder([CompletedProc(1, "", "Error: 401 Unauthorized")])
    with pytest.raises(EngineAuthError):
        DummyEngine(runner=r).run("p")


def test_rate_limit_is_retryable() -> None:
    r = Recorder([CompletedProc(1, "", "Error: 429 too many requests")])
    with pytest.raises(EngineRetryable):
        DummyEngine(runner=r).run("p")
