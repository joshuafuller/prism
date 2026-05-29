# 0014. AST-based risk escalation

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Size/path risk tiers (ADR-0013) under-review small-but-dangerous changes: a 2-line diff
that adds `eval(user_input)` or `subprocess(..., shell=True)` is `trivial` by line count
and may sit outside a security-sensitive path, so the security reviewer never runs. The
construct, not the size, is the risk.

## Decision

Add an **AST signal** that escalates a change to `full` when it *introduces* a risky
construct. For each changed Python file we parse the **new file** with the stdlib `ast`
module, find risky calls, and keep only those on lines the diff **added** (so pre-existing
risky code in an otherwise-trivial change does not over-trigger). Detected constructs:
`eval` / `exec` / `compile` / `__import__`, `os.system` / `os.popen`,
`subprocess(..., shell=True)`, `pickle.load(s)` / `marshal.loads`, `yaml.load`.

Non-Python files and unparseable sources yield no AST signal (skipped). When the signal
fires, the tier becomes `full` and the triggering constructs are recorded in the review
context/report (visible, never silent — ADR-0012).

## Consequences

- Small, dangerous changes get a full review even when size/path heuristics wouldn't.
- The pure detectors (`risky_lines`, `added_line_numbers`) are unit-testable without IO;
  file reading lives in the CLI integration.
- Python-only for now; multi-language (tree-sitter) is future work (prism-se6.9 lineage).
- Errs toward *more* review on uncertainty (safe direction).
