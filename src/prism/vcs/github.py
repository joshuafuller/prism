"""GitHub VCS provider backed by the ``gh`` CLI (reuses the user's gh login)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable

# Runs gh with optional stdin and returns stdout (raises CalledProcessError on failure).
GhRunner = Callable[[list[str], str], str]


def _gh_run(argv: list[str], stdin: str = "") -> str:
    return subprocess.run(argv, input=stdin, check=True, capture_output=True, text=True).stdout


class GitHubProvider:
    def __init__(self, run: GhRunner = _gh_run) -> None:
        self._run = run

    def auth_account(self) -> str:
        return self._run(["gh", "api", "user", "--jq", ".login"], "").strip()

    def post_summary(self, pr: int, body: str) -> None:
        # Body via stdin (--body-file -) so large reports never hit ARG_MAX.
        self._run(["gh", "pr", "comment", str(pr), "--body-file", "-"], body)
