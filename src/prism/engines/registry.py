"""Build Engine instances from configuration.

Maps each ``EngineConfig.kind`` to a concrete engine. API engines are deferred
(prism-4gf.13); requesting one raises ``NotImplementedError`` with a clear message.
"""

from __future__ import annotations

from prism.config import Config, EngineConfig
from prism.engines.base import Engine
from prism.engines.claude_cli import ClaudeCLIEngine
from prism.engines.codex_cli import CodexCLIEngine


def build_engine(config: EngineConfig) -> Engine:
    """Instantiate the engine for a single ``EngineConfig``."""
    match config.kind:
        case "claude-cli":
            return ClaudeCLIEngine()
        case "codex-cli":
            return CodexCLIEngine()
        case "anthropic-api" | "openai-api":
            raise NotImplementedError(
                f"API engine {config.kind!r} is deferred (prism-4gf.13); "
                "use a subscription CLI engine for now."
            )


def build_engines(config: Config) -> dict[str, Engine]:
    """Instantiate every named engine in a Config, keyed by engine name."""
    return {name: build_engine(ec) for name, ec in config.engines.items()}
