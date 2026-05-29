#!/usr/bin/env sh
# Lint staged Python files with ruff (check + format). Fast; runs in pre-commit.
# Uses `uvx ruff` so it works with no project venv. Config: ruff.toml.
set -eu

files=$(git diff --cached --name-only --diff-filter=ACM -- '*.py' || true)
if [ -z "$files" ]; then
    exit 0
fi

echo "prism: ruff check + format --check on staged Python files"
# shellcheck disable=SC2086
echo "$files" | tr '\n' '\0' | xargs -0 uvx ruff check --
# shellcheck disable=SC2086
echo "$files" | tr '\n' '\0' | xargs -0 uvx ruff format --check --
