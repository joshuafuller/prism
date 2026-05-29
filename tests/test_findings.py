from prism.findings import Decision, Finding, ReviewResult, Severity


def _finding(**over: object) -> Finding:
    base: dict[str, object] = {
        "id": "x1",
        "severity": Severity.WARNING,
        "category": "security",
        "file": "a.py",
        "line": 10,
        "title": "Session cookie not marked Secure",
        "explanation": "The changed code creates a session cookie without the Secure flag.",
        "recommendation": "Set Secure=True when issuing cookies over HTTPS.",
        "confidence": "high",
        "reviewer": "security",
    }
    base.update(over)
    return Finding(**base)  # type: ignore[arg-type]


def test_finding_roundtrips_through_dump() -> None:
    f = _finding()
    assert f.severity is Severity.WARNING
    assert Finding.model_validate(f.model_dump()) == f


def test_invalid_severity_rejected() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _finding(severity="catastrophic")


def test_decision_blocks_only_on_significant_concerns() -> None:
    assert Decision.SIGNIFICANT_CONCERNS.blocks is True
    assert Decision.APPROVED.blocks is False
    assert Decision.APPROVED_WITH_COMMENTS.blocks is False
    assert Decision.MINOR_ISSUES.blocks is False


def test_decision_severity_ordering() -> None:
    assert Decision.SIGNIFICANT_CONCERNS.at_least(Decision.MINOR_ISSUES)
    assert Decision.MINOR_ISSUES.at_least(Decision.MINOR_ISSUES)
    assert not Decision.APPROVED.at_least(Decision.MINOR_ISSUES)
    assert Decision.SIGNIFICANT_CONCERNS.rank > Decision.APPROVED.rank


def test_review_result_holds_findings_and_decision() -> None:
    rr = ReviewResult(findings=[_finding()], decision=Decision.APPROVED_WITH_COMMENTS, summary="ok")
    assert len(rr.findings) == 1
    assert rr.decision is Decision.APPROVED_WITH_COMMENTS
