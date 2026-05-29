"""Runtime configuration: typed models for ``prism.yaml`` and a loader.

The loader validates that every reviewer/coordinator references a defined engine and
applies environment overrides for engine models (so a model can be bumped without
editing the file): ``PRISM_ENGINE_<NAME>_MODEL`` overrides ``engines[<name>].model``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from prism.engines.base import Effort
from prism.findings import Decision
from prism.risk import RiskTier

EngineKind = Literal["claude-cli", "codex-cli", "anthropic-api", "openai-api"]


class EngineConfig(BaseModel):
    kind: EngineKind
    model: str | None = None
    key_env: str | None = None


class ReviewerConfig(BaseModel):
    engine: str
    effort: Effort = Effort.MEDIUM
    min_tier: RiskTier = RiskTier.TRIVIAL  # runs when assessed tier >= this (ADR-0013)


class CoordinatorConfig(BaseModel):
    engine: str
    effort: Effort = Effort.HIGH


class PolicyConfig(BaseModel):
    fail_on: Decision = Decision.SIGNIFICANT_CONCERNS


class Config(BaseModel):
    engines: dict[str, EngineConfig]
    reviewers: dict[str, ReviewerConfig]
    coordinator: CoordinatorConfig
    policy: PolicyConfig = PolicyConfig()
    # Generous default so large/throttled reviews don't get a reviewer killed mid-flight.
    per_reviewer_timeout: float = 600.0

    @model_validator(mode="after")
    def _engine_refs_must_exist(self) -> Config:
        defined = set(self.engines)
        refs = {name: rc.engine for name, rc in self.reviewers.items()}
        refs["coordinator"] = self.coordinator.engine
        for owner, engine in refs.items():
            if engine not in defined:
                raise ValueError(
                    f"{owner!r} references undefined engine {engine!r}; "
                    f"defined engines: {sorted(defined)}"
                )
        return self


def _env_key(engine_name: str) -> str:
    return "PRISM_ENGINE_" + engine_name.upper().replace("-", "_") + "_MODEL"


def load_config(path: str | Path) -> Config:
    """Load and validate a Prism config, applying env model overrides."""
    data = yaml.safe_load(Path(path).read_text())
    config = Config.model_validate(data)
    for name, engine in config.engines.items():
        override = os.environ.get(_env_key(name))
        if override:
            engine.model = override
    return config
