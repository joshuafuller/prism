from pathlib import Path

import pytest
from pydantic import ValidationError

from prism.config import Config, load_config
from prism.engines.base import Effort
from prism.findings import Decision

EXAMPLE = Path(__file__).resolve().parent.parent / "prism.example.yaml"


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "prism.yaml"
    p.write_text(text)
    return p


def test_timeout_defaults_and_override(tmp_path: Path) -> None:
    cfg = load_config(EXAMPLE)
    assert cfg.inactivity_timeout == 120.0  # liveness window default
    assert cfg.overall_timeout == 1500.0  # generous backstop default
    p = _write(
        tmp_path,
        """
engines:
  claude-cli: {kind: claude-cli}
reviewers:
  security: {engine: claude-cli, effort: high}
coordinator: {engine: claude-cli, effort: high}
inactivity_timeout: 90
overall_timeout: 1800
""",
    )
    cfg2 = load_config(p)
    assert cfg2.inactivity_timeout == 90.0
    assert cfg2.overall_timeout == 1800.0


def test_loads_example_config() -> None:
    cfg = load_config(EXAMPLE)
    assert isinstance(cfg, Config)
    assert cfg.engines["claude-cli"].kind == "claude-cli"
    assert cfg.reviewers["security"].engine == "codex-cli"
    assert cfg.reviewers["security"].effort is Effort.HIGH
    assert cfg.coordinator.engine == "claude-cli"
    assert cfg.policy.fail_on is Decision.SIGNIFICANT_CONCERNS


def test_reviewer_referencing_unknown_engine_is_rejected(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        """
engines:
  claude-cli: {kind: claude-cli}
reviewers:
  security: {engine: nonexistent, effort: high}
coordinator: {engine: claude-cli, effort: high}
""",
    )
    with pytest.raises(ValidationError):
        load_config(bad)


def test_coordinator_referencing_unknown_engine_is_rejected(tmp_path: Path) -> None:
    bad = _write(
        tmp_path,
        """
engines:
  claude-cli: {kind: claude-cli}
reviewers:
  security: {engine: claude-cli, effort: high}
coordinator: {engine: ghost, effort: high}
""",
    )
    with pytest.raises(ValidationError):
        load_config(bad)


def test_env_overrides_engine_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = _write(
        tmp_path,
        """
engines:
  anthropic: {kind: anthropic-api, key_env: ANTHROPIC_API_KEY, model: claude-opus-4-7}
reviewers:
  security: {engine: anthropic, effort: high}
coordinator: {engine: anthropic, effort: high}
""",
    )
    monkeypatch.setenv("PRISM_ENGINE_ANTHROPIC_MODEL", "claude-opus-4-8")
    cfg = load_config(cfg_path)
    assert cfg.engines["anthropic"].model == "claude-opus-4-8"
