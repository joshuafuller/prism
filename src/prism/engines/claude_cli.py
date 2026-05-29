"""Engine backed by the ``claude`` CLI (Claude Code), using the Max subscription.

Runs ``claude -p --output-format stream-json --verbose`` with the prompt on stdin, and
parses the emitted JSONL events for the final text and token usage. No model version is
hardcoded: when ``model`` is omitted the CLI uses the subscription's current default.

Note on effort: Claude Code does not expose a reasoning-effort CLI flag, so ``effort`` is
accepted (for a uniform Engine interface) but not translated into argv here. The effort
knob (ADR-0006) is realized on the codex engine and via model selection.
"""

from __future__ import annotations

import json

from prism.engines.base import Effort, Engine, ParsedResult


class ClaudeCLIEngine(Engine):
    name = "claude-cli"

    def _build_argv(self, effort: Effort, model: str | None) -> list[str]:
        argv = ["claude", "-p", "--output-format", "stream-json", "--verbose"]
        if model:
            argv += ["--model", model]
        return argv

    def _parse(self, stdout: str) -> ParsedResult:
        text = ""
        tokens_in = 0
        tokens_out = 0
        finish_reason: str | None = None

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            etype = event.get("type")
            if etype == "assistant":
                message = event.get("message")
                if isinstance(message, dict):
                    stop = message.get("stop_reason")
                    if stop:
                        finish_reason = "length" if stop == "max_tokens" else stop
                    usage = message.get("usage")
                    if isinstance(usage, dict):
                        tokens_in = usage.get("input_tokens", tokens_in)
                        tokens_out = usage.get("output_tokens", tokens_out)
            elif etype == "result":
                if isinstance(event.get("result"), str):
                    text = event["result"]
                usage = event.get("usage")
                if isinstance(usage, dict):
                    tokens_in = usage.get("input_tokens", tokens_in)
                    tokens_out = usage.get("output_tokens", tokens_out)

        return ParsedResult(
            text=text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            finish_reason=finish_reason,
        )
