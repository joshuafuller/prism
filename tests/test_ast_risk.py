"""Tests for the AST risk detector.

The eval/pickle/os.system/shell=True snippets below are **string fixtures** parsed by the
detector to verify it flags them. They are data for `ast.parse`, never executed.
"""

from prism.ast_risk import added_line_numbers, ast_risk_labels, risky_lines


def test_risky_lines_detects_common_constructs() -> None:
    src = (
        "import os, subprocess, pickle\n"
        "def f(x):\n"
        "    a = eval(x)\n"
        "    os.system(x)\n"
        "    subprocess.run(x, shell=True)\n"
        "    pickle.loads(x)\n"
        "    return a\n"
    )
    labels = set(risky_lines(src).values())
    assert "eval" in labels
    assert "os.system" in labels
    assert "subprocess.run(shell=True)" in labels
    assert "pickle.loads" in labels


def test_risky_lines_ignores_safe_code() -> None:
    assert risky_lines("def add(a, b):\n    return a + b\n") == {}


def test_subprocess_without_shell_true_is_not_risky() -> None:
    assert risky_lines("import subprocess\nsubprocess.run(['ls'])\n") == {}


def test_risky_lines_returns_empty_on_non_python() -> None:
    assert risky_lines("this is not : valid python {{{") == {}


def test_added_line_numbers_parses_hunk() -> None:
    patch = (
        "diff --git a/m.py b/m.py\n"
        "--- a/m.py\n"
        "+++ b/m.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def f(x):\n"
        "+    y = eval(x)\n"
        "     return x\n"
    )
    # new lines: 1 (context), 2 (added), 3 (context) -> added = {2}
    assert added_line_numbers(patch) == {2}


def test_ast_risk_labels_only_flags_constructs_on_added_lines() -> None:
    new_source = "def f(x):\n    y = eval(x)\n    return y\n"  # eval on line 2
    added_patch = "@@ -1,2 +1,3 @@\n def f(x):\n+    y = eval(x)\n     return y\n"
    assert ast_risk_labels(new_source, added_patch) == ["eval"]

    # same risky source, but the eval line was NOT added (only the return changed)
    unchanged_patch = "@@ -3,1 +3,1 @@\n-    return None\n+    return y\n"
    assert ast_risk_labels(new_source, unchanged_patch) == []
