"""Engine backed by the ``codex`` CLI, using the ChatGPT subscription.

Runs ``codex exec --json --skip-git-repo-check`` with the prompt on stdin, mapping the
reasoning-effort knob (ADR-0006) to codex's ``model_reasoning_effort`` config and parsing
the JSONL event stream for the final agent message and token usage.

The exact codex JSON event schema is confirmed by the live test (prism-4gf.26); this
parser is tolerant of unknown event types.
"""

from __future__ import annotations

import json

from prism.engines.base import Effort, Engine, ParsedResult, merge_usage

# Our Effort vocabulary mapped to codex's accepted reasoning-effort values.
_EFFORT_TO_CODEX: dict[Effort, str] = {
    Effort.LOW: "low",
    Effort.MEDIUM: "medium",
    Effort.HIGH: "high",
    Effort.XHIGH: "xhigh",
    Effort.MAX: "xhigh",
}


class CodexCLIEngine(Engine):
    name = "codex-cli"

    def _build_argv(self, effort: Effort, model: str | None) -> list[str]:
        codex_effort = _EFFORT_TO_CODEX[effort]
        argv = [
            "codex",
            "exec",
            "--json",
            "--skip-git-repo-check",
            "-c",
            f'model_reasoning_effort="{codex_effort}"',
        ]
        if model:
            argv += ["--model", model]
        return argv

    def _parse(self, stdout: str) -> ParsedResult:
        text = ""
        tokens_in = 0
        tokens_out = 0

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
            if etype == "item.completed":
                item = event.get("item", {})
                if (
                    isinstance(item, dict)
                    and item.get("type") == "agent_message"
                    and isinstance(item.get("text"), str)
                ):
                    text = item["text"]
            elif etype == "turn.completed":
                tokens_in, tokens_out = merge_usage(event, tokens_in, tokens_out)

        return ParsedResult(text=text, tokens_in=tokens_in, tokens_out=tokens_out)
