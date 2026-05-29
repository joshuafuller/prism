"""Diff sources: turn a git/PR diff into per-file patches.

A ``DiffSource`` yields ``ChangedFile`` entries (path + unified patch + line counts).
``GitDiffSource`` shells out to ``git diff``; ``GhPrDiffSource`` to ``gh pr diff``. Both
parse the unified diff with the shared ``parse_unified_diff`` (DRY).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Runs a command and returns its stdout (raises CalledProcessError on failure).
CmdRunner = Callable[[list[str]], str]

_FILE_SPLIT = re.compile(r"(?m)^(?=diff --git )")
_NEW_PATH = re.compile(r"(?m)^\+\+\+ b/(.+)$")
_GIT_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ChangedFile:
    path: str
    patch: str
    added: int
    removed: int


def _count_lines(chunk: str, sign: str, header_prefix: str) -> int:
    return sum(
        1 for ln in chunk.splitlines() if ln.startswith(sign) and not ln.startswith(header_prefix)
    )


def parse_unified_diff(text: str) -> list[ChangedFile]:
    """Parse a unified diff into per-file ChangedFile entries."""
    files: list[ChangedFile] = []
    for chunk in _FILE_SPLIT.split(text):
        if not chunk.startswith("diff --git"):
            continue
        new_path = _NEW_PATH.search(chunk)
        if new_path and new_path.group(1) != "/dev/null":
            path = new_path.group(1)
        else:
            header = _GIT_HEADER.search(chunk)
            path = header.group(2) if header else "unknown"
        files.append(
            ChangedFile(
                path=path,
                patch=chunk,
                added=_count_lines(chunk, "+", "+++"),
                removed=_count_lines(chunk, "-", "---"),
            )
        )
    return files


def _run_text(argv: list[str]) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout


class GitDiffSource:
    """Changed files from ``git diff <target>`` in a repo working tree."""

    def __init__(self, target: str, repo: Path | str = ".", run: CmdRunner = _run_text) -> None:
        self._target = target
        self._repo = str(repo)
        self._run = run

    def changed_files(self) -> list[ChangedFile]:
        diff = self._run(["git", "-C", self._repo, "diff", self._target, "--"])
        return parse_unified_diff(diff)


class GhPrDiffSource:
    """Changed files from ``gh pr diff <pr>`` (GitHub)."""

    def __init__(self, pr: int, run: CmdRunner = _run_text) -> None:
        self._pr = pr
        self._run = run

    def changed_files(self) -> list[ChangedFile]:
        diff = self._run(["gh", "pr", "diff", str(self._pr), "--patch"])
        return parse_unified_diff(diff)
