import json
from collections.abc import Callable

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


def _ok(
    make_proc: Callable[..., CompletedProc], text: str = "hi", finish: str = "stop"
) -> CompletedProc:
    return make_proc(json.dumps({"text": text, "in": 5, "out": 3, "finish": finish}))


def test_prompt_goes_to_stdin_not_argv(fake_runner, make_proc) -> None:
    r = fake_runner([_ok(make_proc)])
    DummyEngine(runner=r).run("HELLO-PROMPT", effort=Effort.LOW)
    assert "HELLO-PROMPT" not in " ".join(r.last_argv)
    assert r.last_stdin == "HELLO-PROMPT"


def test_parses_text_and_token_usage(fake_runner, make_proc) -> None:
    proc = make_proc(json.dumps({"text": "reviewed", "in": 10, "out": 20, "finish": "stop"}))
    res = DummyEngine(runner=fake_runner([proc])).run("p")
    assert res.text == "reviewed"
    assert res.tokens_in == 10
    assert res.tokens_out == 20


def test_truncation_retries_once_then_returns_full(fake_runner, make_proc) -> None:
    r = fake_runner([_ok(make_proc, text="cut", finish="length"), _ok(make_proc, text="full")])
    res = DummyEngine(runner=r).run("p")
    assert len(r.calls) == 2
    assert res.text == "full"
    assert res.finish_reason == "stop"


def test_timeout_raises_engine_timeout(fake_runner) -> None:
    r = fake_runner([], raise_timeout=True)
    with pytest.raises(EngineTimeout):
        DummyEngine(runner=r).run("p")


def test_auth_error_is_not_retryable(fake_runner, make_proc) -> None:
    r = fake_runner([make_proc("", code=1, stderr="Error: 401 Unauthorized")])
    with pytest.raises(EngineAuthError):
        DummyEngine(runner=r).run("p")


def test_rate_limit_is_retryable(fake_runner, make_proc) -> None:
    r = fake_runner([make_proc("", code=1, stderr="Error: 429 too many requests")])
    with pytest.raises(EngineRetryable):
        DummyEngine(runner=r).run("p")
