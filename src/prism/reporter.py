"""Render a ReviewResult as a markdown report (for the terminal and PR comments)."""

from __future__ import annotations

from prism.findings import Finding, ReviewResult, Severity

_LIMITATIONS = (
    "_Prism is an AI first-pass, **not a replacement for human review**. It can miss "
    "architectural intent, cross-system impact, and subtle concurrency bugs._"
)
_SEVERITY_ORDER = (Severity.CRITICAL, Severity.WARNING, Severity.SUGGESTION)


def _render_finding(finding: Finding) -> str:
    return (
        f"- **{finding.title}** — `{finding.file}:{finding.line}` "
        f"({finding.reviewer}, {finding.confidence} confidence)\n"
        f"  - {finding.explanation}\n"
        f"  - _Fix:_ {finding.recommendation}"
    )


def to_markdown(result: ReviewResult, *, skipped: list[tuple[str, str]] | None = None) -> str:
    lines = [f"# Prism review: {result.decision.value}", "", result.summary]

    if result.findings:
        for severity in _SEVERITY_ORDER:
            group = [f for f in result.findings if f.severity is severity]
            if not group:
                continue
            lines.append("")
            lines.append(f"## {severity.value.title()} ({len(group)})")
            lines.extend(_render_finding(f) for f in group)
    else:
        lines.append("")
        lines.append("No findings. 🎉")

    # No silent truncation (ADR-0012): an incomplete review must look incomplete.
    if skipped:
        lines.append("")
        lines.append(f"## Reviewers skipped ({len(skipped)})")
        lines.extend(f"- **{name}** — {reason}" for name, reason in skipped)

    lines.extend(["", "---", _LIMITATIONS])
    return "\n".join(lines) + "\n"
