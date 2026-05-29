import json

from prism.engines.base import Effort
from prism.engines.claude_cli import ClaudeCLIEngine


def _stream(*events: dict[str, object]) -> str:
    return "\n".join(json.dumps(e) for e in events)


def test_argv_uses_stream_json_and_keeps_prompt_off_argv(fake_runner, make_proc) -> None:
    r = fake_runner([make_proc(_stream({"type": "result", "result": "ok"}))])
    ClaudeCLIEngine(runner=r).run("SECRET-PROMPT", effort=Effort.HIGH)
    argv = r.last_argv
    assert argv[0] == "claude"
    assert "--output-format" in argv
    assert "stream-json" in argv
    assert "SECRET-PROMPT" not in " ".join(argv)
    assert r.last_stdin == "SECRET-PROMPT"


def test_model_flag_added_only_when_given(fake_runner, make_proc) -> None:
    proc = make_proc(_stream({"type": "result", "result": "ok"}))
    r1 = fake_runner([proc])
    ClaudeCLIEngine(runner=r1).run("p", model="claude-opus-4-8")
    assert "--model" in r1.last_argv
    assert "claude-opus-4-8" in r1.last_argv

    r2 = fake_runner([proc])
    ClaudeCLIEngine(runner=r2).run("p")
    assert "--model" not in r2.last_argv


def test_parses_result_text_and_usage(fake_runner, make_proc) -> None:
    out = _stream(
        {"type": "system", "subtype": "init"},
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "hi"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 34},
            },
        },
        {"type": "result", "subtype": "success", "result": "final text"},
    )
    res = ClaudeCLIEngine(runner=fake_runner([make_proc(out)])).run("p")
    assert res.text == "final text"
    assert res.tokens_in == 12
    assert res.tokens_out == 34
    assert res.finish_reason == "end_turn"


def test_max_tokens_stop_reason_maps_to_length_and_triggers_retry(fake_runner, make_proc) -> None:
    truncated = _stream(
        {"type": "assistant", "message": {"stop_reason": "max_tokens", "usage": {}}},
        {"type": "result", "result": "partial"},
    )
    complete = _stream({"type": "result", "result": "complete"})
    r = fake_runner([make_proc(truncated), make_proc(complete)])
    res = ClaudeCLIEngine(runner=r).run("p")
    assert len(r.calls) == 2
    assert res.text == "complete"
