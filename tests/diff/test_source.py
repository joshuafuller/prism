import subprocess
from pathlib import Path

from prism.diff.source import GhPrDiffSource, GitDiffSource, parse_unified_diff

SAMPLE_DIFF = """diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1 +1 @@
-x = 1
+x = 2
diff --git a/b.py b/b.py
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/b.py
@@ -0,0 +1 @@
+print("hi")
"""


def test_parse_unified_diff_extracts_files_patches_and_counts() -> None:
    files = parse_unified_diff(SAMPLE_DIFF)
    by_path = {f.path: f for f in files}
    assert set(by_path) == {"a.py", "b.py"}
    assert "x = 2" in by_path["a.py"].patch
    assert by_path["a.py"].added == 1
    assert by_path["a.py"].removed == 1
    assert by_path["b.py"].added == 1
    assert by_path["b.py"].removed == 0


def test_parse_unified_diff_empty_is_no_files() -> None:
    assert parse_unified_diff("") == []


def test_git_diff_source_against_fixture_repo(git_repo: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(git_repo), *args], check=True, capture_output=True, text=True
        )

    git("checkout", "-q", "-b", "feature")
    (git_repo / "a.py").write_text("x = 2\n")
    (git_repo / "b.py").write_text('print("hi")\n')
    git("add", "-A")
    git("commit", "-q", "-m", "change")

    files = GitDiffSource(target="main", repo=git_repo).changed_files()
    by_path = {f.path: f for f in files}
    assert set(by_path) == {"a.py", "b.py"}
    assert "x = 2" in by_path["a.py"].patch


def test_gh_pr_diff_source_invokes_gh_and_parses() -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(argv: list[str]) -> str:
        captured["argv"] = argv
        return SAMPLE_DIFF

    files = GhPrDiffSource(pr=42, run=fake_run).changed_files()
    assert captured["argv"][:3] == ["gh", "pr", "diff"]
    assert "42" in captured["argv"]
    assert {f.path for f in files} == {"a.py", "b.py"}
