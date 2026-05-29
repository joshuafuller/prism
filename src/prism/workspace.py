"""Build the on-disk review workspace under ``.prism/``.

The full diff is written to disk **once** as per-file patches; reviewers receive paths
and read only what their domain needs, rather than each prompt embedding the whole diff
(token frugality — see the Cloudflare lessons). The shared context holds metadata only,
never the patch bodies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from prism.diff.source import ChangedFile


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path  # the .prism directory
    shared_context_path: Path
    changed_files_path: Path
    patch_dir: Path
    patch_paths: dict[str, Path]  # original file path -> on-disk patch file


def _flatten(path: str) -> str:
    return path.replace("/", "__") + ".patch"


def build_workspace(files: list[ChangedFile], shared_context: str, root: Path | str) -> Workspace:
    """Write `.prism/` (shared context, manifest, per-file patches) under ``root``."""
    ws_root = Path(root) / ".prism"
    patch_dir = ws_root / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)

    shared_context_path = ws_root / "shared-context.txt"
    shared_context_path.write_text(shared_context)

    manifest = [{"path": f.path, "added": f.added, "removed": f.removed} for f in files]
    changed_files_path = ws_root / "changed-files.json"
    changed_files_path.write_text(json.dumps(manifest, indent=2))

    patch_paths: dict[str, Path] = {}
    for file in files:
        patch_path = patch_dir / _flatten(file.path)
        patch_path.write_text(file.patch)
        patch_paths[file.path] = patch_path

    return Workspace(
        root=ws_root,
        shared_context_path=shared_context_path,
        changed_files_path=changed_files_path,
        patch_dir=patch_dir,
        patch_paths=patch_paths,
    )
