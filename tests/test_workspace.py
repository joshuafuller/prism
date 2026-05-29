import json
from pathlib import Path

from prism.diff.source import ChangedFile
from prism.workspace import build_workspace


def _files() -> list[ChangedFile]:
    return [
        ChangedFile(path="src/app.py", patch="@@ app patch @@\n+x = 2\n", added=1, removed=0),
        ChangedFile(
            path="db/migrations/001.sql",
            patch="@@ sql @@\n+ALTER TABLE t;\n",
            added=1,
            removed=0,
        ),
    ]


def test_writes_shared_context_changed_files_and_patches(tmp_path: Path) -> None:
    ws = build_workspace(_files(), shared_context="TITLE: fix\nTARGET: main", root=tmp_path)

    assert ws.shared_context_path.read_text() == "TITLE: fix\nTARGET: main"

    manifest = json.loads(ws.changed_files_path.read_text())
    assert {e["path"] for e in manifest} == {"src/app.py", "db/migrations/001.sql"}
    assert manifest[0]["added"] == 1

    # one patch file per changed file, names flattened
    assert ws.patch_paths["src/app.py"].read_text() == "@@ app patch @@\n+x = 2\n"
    assert ws.patch_paths["src/app.py"].name == "src__app.py.patch"


def test_full_patch_lives_on_disk_not_in_shared_context(tmp_path: Path) -> None:
    ws = build_workspace(_files(), shared_context="metadata only", root=tmp_path)
    # token-frugality: the shared context must NOT embed the patch bodies
    assert "ALTER TABLE" not in ws.shared_context_path.read_text()
    assert "ALTER TABLE" in ws.patch_paths["db/migrations/001.sql"].read_text()


def test_workspace_lives_under_dot_prism(tmp_path: Path) -> None:
    ws = build_workspace(_files(), shared_context="x", root=tmp_path)
    assert ws.root == tmp_path / ".prism"
    assert ws.patch_dir == tmp_path / ".prism" / "patches"
