"""Live smoke tests: run the real subscription CLIs (excluded from the default suite).

Run with: uv run pytest -m live
Proves the engine parsers handle real claude/codex output end-to-end (no fakes).
"""

import pytest

from prism.engines.base import Effort
from prism.engines.claude_cli import ClaudeCLIEngine
from prism.engines.codex_cli import CodexCLIEngine

_PROMPT = "Reply with exactly this token and nothing else: PRISM_LIVE_OK"


@pytest.mark.live
def test_claude_cli_live_smoke() -> None:
    result = ClaudeCLIEngine().run(_PROMPT, effort=Effort.LOW)
    assert "PRISM_LIVE_OK" in result.text


@pytest.mark.live
def test_codex_cli_live_smoke() -> None:
    result = CodexCLIEngine().run(_PROMPT, effort=Effort.LOW)
    assert "PRISM_LIVE_OK" in result.text
