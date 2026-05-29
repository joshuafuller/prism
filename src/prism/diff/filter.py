"""Filter noisy files out of a diff before review.

Skips lock files, minified/bundled assets, source maps, and clearly generated files —
but **never** database/schema migrations, even when they carry generated markers (a
lesson from Cloudflare: migration tools stamp files as generated yet the schema changes
must be reviewed). Skipped files are returned with a reason; nothing is dropped silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from prism.diff.source import ChangedFile

NOISE_FILES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lock",
        "go.sum",
        "Cargo.lock",
        "poetry.lock",
        "Pipfile.lock",
        "flake.lock",
    }
)
NOISE_SUFFIXES = (".min.js", ".min.css", ".bundle.js", ".map")
_GENERATED_MARKERS = ("@generated", "eslint-disable")
_MIGRATION = re.compile(r"(^|/)(migrations?|migrate)(/|_|$)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FilterResult:
    kept: list[ChangedFile]
    skipped: list[tuple[str, str]]  # (path, reason)


def _is_migration(path: str) -> bool:
    return _MIGRATION.search(path) is not None


def _looks_generated(patch: str) -> bool:
    for line in patch.splitlines():
        if line.startswith("+") and any(marker in line for marker in _GENERATED_MARKERS):
            return True
    return False


def _skip_reason(file: ChangedFile) -> str | None:
    """Reason this file should be skipped, or None to keep it."""
    name = file.path.rsplit("/", 1)[-1]
    if name in NOISE_FILES:
        return "lock file"
    if file.path.endswith(NOISE_SUFFIXES):
        return "minified/bundled/source-map asset"
    if _is_migration(file.path):
        return None  # migrations are always reviewed, even if generated-looking
    if _looks_generated(file.patch):
        return "generated file (marker in added lines)"
    return None


def filter_diff(files: list[ChangedFile]) -> FilterResult:
    kept: list[ChangedFile] = []
    skipped: list[tuple[str, str]] = []
    for file in files:
        reason = _skip_reason(file)
        if reason is None:
            kept.append(file)
        else:
            skipped.append((file.path, reason))
    return FilterResult(kept=kept, skipped=skipped)
