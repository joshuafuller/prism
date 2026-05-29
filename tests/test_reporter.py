from prism.findings import Decision, Finding, ReviewResult
from prism.reporter import to_markdown


def _f(severity: str, title: str) -> Finding:
    return Finding(
        id=title,
        severity=severity,  # type: ignore[arg-type]
        category="security",
        file="a.py",
        line=7,
        title=title,
        explanation="why",
        recommendation="fix it",
        confidence="high",
        reviewer="security",
    )


def test_renders_decision_header_and_summary() -> None:
    result = ReviewResult(findings=[], decision=Decision.APPROVED, summary="All clear.")
    md = to_markdown(result)
    assert "approved" in md
    assert "All clear." in md


def test_groups_findings_by_severity() -> None:
    result = ReviewResult(
        findings=[_f("critical", "Crit bug"), _f("warning", "Warn bug")],
        decision=Decision.SIGNIFICANT_CONCERNS,
        summary="s",
    )
    md = to_markdown(result)
    assert "Critical" in md and "Crit bug" in md
    assert "Warning" in md and "Warn bug" in md
    # critical section appears before warning section
    assert md.index("Critical") < md.index("Warning")


def test_empty_findings_reads_as_no_findings() -> None:
    md = to_markdown(ReviewResult(findings=[], decision=Decision.APPROVED, summary="s"))
    assert "No findings" in md


def test_includes_limitations_note() -> None:
    md = to_markdown(ReviewResult(findings=[], decision=Decision.APPROVED, summary="s"))
    assert "not a replacement for human review" in md.lower()


def test_renders_skipped_reviewers_section() -> None:
    result = ReviewResult(findings=[], decision=Decision.APPROVED, summary="s")
    md = to_markdown(result, skipped=[("security", "timed out after 300s")])
    assert "Reviewers skipped" in md
    assert "security" in md
    assert "timed out after 300s" in md


def test_no_skipped_section_when_none_skipped() -> None:
    md = to_markdown(ReviewResult(findings=[], decision=Decision.APPROVED, summary="s"))
    assert "Reviewers skipped" not in md


def test_suggestion_severity_rendered() -> None:
    result = ReviewResult(
        findings=[_f("suggestion", "Nice to have")],
        decision=Decision.APPROVED_WITH_COMMENTS,
        summary="s",
    )
    assert "Suggestion" in to_markdown(result)
