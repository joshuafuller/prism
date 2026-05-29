# 0003. Python + uv (no pip / no manual venvs)

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Prism is an orchestrator that drives CLIs via subprocess, talks to GitHub/GitLab, and
validates structured findings. It needs fast TDD iteration. The owner explicitly wants
`uv` and to avoid pip and hand-managed virtualenv messes. Language candidates were
Python, TypeScript/Node, and Go.

## Decision

We will build Prism in **Python**, managed exclusively with **uv**. No pip, no
hand-rolled venvs. `uv init` scaffolds `pyproject.toml`; dependencies via `uv add`;
all commands run through `uv run …`; `uv.lock` is committed. Pydantic validates finding
schemas; pytest + pytest-mock drive TDD; ruff + mypy gate quality.

## Consequences

- Clean subprocess control for the CLI engines; mature `PyGithub` / `python-gitlab`;
  pydantic gives schema validation + repair-retry cheaply; pytest makes the fast unit
  loop sub-second.
- uv gives reproducible, fast env management with a single lockfile and no venv drift.
- Trade-off vs Go: not a single static binary — but the Docker image is the distribution
  unit anyway, so this matters little.
- Trade-off vs TypeScript: does not reuse the OpenCode plugin ecosystem the reference
  design references; acceptable since Prism owns its orchestration.
- Reversing the language is a rewrite; reversing uv (e.g. to Poetry) is mechanical.
