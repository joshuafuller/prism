from pathlib import Path

import pytest

from prism.config import EngineConfig, load_config
from prism.engines.claude_cli import ClaudeCLIEngine
from prism.engines.codex_cli import CodexCLIEngine
from prism.engines.registry import build_engine, build_engines

EXAMPLE = Path(__file__).resolve().parents[2] / "prism.example.yaml"


def test_build_engine_claude_cli() -> None:
    assert isinstance(build_engine(EngineConfig(kind="claude-cli")), ClaudeCLIEngine)


def test_build_engine_codex_cli() -> None:
    assert isinstance(build_engine(EngineConfig(kind="codex-cli")), CodexCLIEngine)


def test_build_engine_api_kind_is_deferred() -> None:
    with pytest.raises(NotImplementedError):
        build_engine(EngineConfig(kind="anthropic-api", key_env="ANTHROPIC_API_KEY"))


def test_build_engine_applies_timeouts() -> None:
    eng = build_engine(EngineConfig(kind="claude-cli"), inactivity_s=90.0, overall_s=1800.0)
    assert eng._inactivity_s == 90.0
    assert eng._overall_s == 1800.0


def test_build_engines_uses_config_timeouts() -> None:
    engines = build_engines(load_config(EXAMPLE))  # example defaults: 120 / 1500
    assert engines["claude-cli"]._inactivity_s == 120.0
    assert engines["claude-cli"]._overall_s == 1500.0


def test_build_engines_maps_each_named_engine() -> None:
    engines = build_engines(load_config(EXAMPLE))
    assert set(engines) == {"claude-cli", "codex-cli"}
    assert isinstance(engines["claude-cli"], ClaudeCLIEngine)
    assert isinstance(engines["codex-cli"], CodexCLIEngine)
