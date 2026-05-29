import json

from prism.engines.base import Effort
from prism.engines.codex_cli import CodexCLIEngine


def _stream(*events: dict[str, object]) -> str:
    return "\n".join(json.dumps(e) for e in events)


def _result(text: str = "ok") -> str:
    return _stream({"type": "item.completed", "item": {"type": "agent_message", "text": text}})


def test_argv_uses_exec_json_skip_git_and_prompt_off_argv(fake_runner, make_proc) -> None:
    r = fake_runner([make_proc(_result())])
    CodexCLIEngine(runner=r).run("SECRET-PROMPT", effort=Effort.HIGH)
    argv = r.last_argv
    assert argv[:2] == ["codex", "exec"]
    assert "--json" in argv
    assert "--skip-git-repo-check" in argv
    assert "SECRET-PROMPT" not in " ".join(argv)
    assert r.last_stdin == "SECRET-PROMPT"


def test_effort_maps_to_model_reasoning_effort(fake_runner, make_proc) -> None:
    r = fake_runner([make_proc(_result())])
    CodexCLIEngine(runner=r).run("p", effort=Effort.MAX)
    joined = " ".join(r.last_argv)
    assert "model_reasoning_effort" in joined
    assert "xhigh" in joined  # MAX maps to codex's xhigh


def test_model_flag_added_only_when_given(fake_runner, make_proc) -> None:
    r1 = fake_runner([make_proc(_result())])
    CodexCLIEngine(runner=r1).run("p", model="gpt-5.5")
    assert "--model" in r1.last_argv
    assert "gpt-5.5" in r1.last_argv

    r2 = fake_runner([make_proc(_result())])
    CodexCLIEngine(runner=r2).run("p")
    assert "--model" not in r2.last_argv


def test_parses_agent_message_and_usage(fake_runner, make_proc) -> None:
    out = _stream(
        {"type": "thread.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "the review"}},
        {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 40}},
    )
    res = CodexCLIEngine(runner=fake_runner([make_proc(out)])).run("p")
    assert res.text == "the review"
    assert res.tokens_in == 100
    assert res.tokens_out == 40
