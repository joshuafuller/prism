#!/usr/bin/env sh
# Full local CI gate: the same checks as .github/workflows/ci.yml.
# Runs on every `git push` via .githooks/pre-push, and can be run by hand:
#   sh scripts/check.sh
set -eu

echo "prism check: ruff lint"
uv run ruff check .

echo "prism check: ruff format"
uv run ruff format --check .

echo "prism check: mypy"
uv run mypy src

echo "prism check: pytest (not live)"
uv run pytest -q

echo "prism check: OK"
