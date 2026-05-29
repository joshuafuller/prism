"""AST-based risk detection (ADR-0014).

Parses the *new* version of a changed Python file and flags risky constructs that the
diff introduced, so a small change can still escalate to a full review. Pure functions
only; file reading happens in the caller. Non-Python / unparseable input yields nothing.
"""

from __future__ import annotations

import ast
import re

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

# Bare-name calls that are risky: eval(...), exec(...), etc.
_RISKY_NAMES = {"eval", "exec", "compile", "__import__"}
# module.attr calls that are risky.
_RISKY_ATTRS = {
    ("os", "system"),
    ("os", "popen"),
    ("pickle", "load"),
    ("pickle", "loads"),
    ("marshal", "loads"),
    ("yaml", "load"),
}


def _call_label(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name) and func.id in _RISKY_NAMES:
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        pair = (func.value.id, func.attr)
        if pair in _RISKY_ATTRS:
            return f"{pair[0]}.{pair[1]}"
        if func.value.id == "subprocess":
            for kw in call.keywords:
                shell_true = (
                    kw.arg == "shell"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                )
                if shell_true:
                    return f"subprocess.{func.attr}(shell=True)"
    return None


def risky_lines(source: str) -> dict[int, str]:
    """Map line number -> risky-construct label for a Python source string."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    found: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            label = _call_label(node)
            if label is not None:
                found[node.lineno] = label
    return found


def added_line_numbers(patch: str) -> set[int]:
    """Line numbers (in the new file) that this unified-diff patch adds."""
    added: set[int] = set()
    new_line = 0
    for line in patch.splitlines():
        hunk = _HUNK.match(line)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if new_line == 0:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue  # removed line: new-file numbering unaffected
        elif line.startswith("\\"):
            continue  # "\ No newline at end of file"
        else:
            new_line += 1  # context line
    return added


def ast_risk_labels(new_source: str, patch: str) -> list[str]:
    """Risky constructs the patch introduced on added lines of ``new_source``."""
    risky = risky_lines(new_source)
    if not risky:
        return []
    added = added_line_numbers(patch)
    return [label for line, label in sorted(risky.items()) if line in added]
