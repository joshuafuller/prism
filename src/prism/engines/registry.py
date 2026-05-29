"""Build Engine instances from configuration.

Maps each ``EngineConfig.kind`` to a concrete engine. API engines are deferred
(prism-4gf.13); requesting one raises ``NotImplementedError`` with a clear message.
"""

from __future__ import annotations

from collections.abc import Callable

from prism.config import Config, EngineConfig
from prism.engines.base import Engine
from prism.engines.claude_cli import ClaudeCLIEngine
from prism.engines.codex_cli import CodexCLIEngine


def build_engine(
    config: EngineConfig,
    *,
    inactivity_s: float = 120.0,
    overall_s: float = 1500.0,
    heartbeat: Callable[[float], None] | None = None,
) -> Engine:
    """Instantiate the engine for a single ``EngineConfig``."""
    match config.kind:
        case "claude-cli":
            return ClaudeCLIEngine(
                inactivity_s=inactivity_s, overall_s=overall_s, heartbeat=heartbeat
            )
        case "codex-cli":
            return CodexCLIEngine(
                inactivity_s=inactivity_s, overall_s=overall_s, heartbeat=heartbeat
            )
        case "anthropic-api" | "openai-api":
            raise NotImplementedError(
                f"API engine {config.kind!r} is deferred (prism-4gf.13); "
                "use a subscription CLI engine for now."
            )


def build_engines(
    config: Config, *, heartbeat: Callable[[float], None] | None = None
) -> dict[str, Engine]:
    """Instantiate every named engine in a Config, keyed by engine name."""
    return {
        name: build_engine(
            ec,
            inactivity_s=config.inactivity_timeout,
            overall_s=config.overall_timeout,
            heartbeat=heartbeat,
        )
        for name, ec in config.engines.items()
    }
