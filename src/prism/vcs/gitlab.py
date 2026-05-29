"""GitLab VCS provider backed by the ``glab`` CLI (reuses the user's glab login)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

# Runs glab with optional stdin and returns stdout (raises CalledProcessError on failure).
GlabRunner = Callable[[list[str], str], str]


def _glab_run(argv: list[str], stdin: str = "") -> str:
    return subprocess.run(argv, input=stdin, check=True, capture_output=True, text=True).stdout


class GitLabProvider:
    def __init__(self, run: GlabRunner = _glab_run) -> None:
        self._run = run

    def auth_account(self) -> str:
        # glab api doesn't support --jq, so parse the JSON ourselves.
        data = json.loads(self._run(["glab", "api", "user"], ""))
        username = data.get("username", "")
        return str(username)

    def post_summary(self, pr: int, body: str) -> None:
        # Body via stdin so large reports never hit ARG_MAX. `pr` is the MR iid.
        self._run(["glab", "mr", "note", "create", str(pr)], body)
