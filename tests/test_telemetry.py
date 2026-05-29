import json
from pathlib import Path

from prism.findings import Decision, Finding, ReviewResult
from prism.telemetry import ReviewRecord, emit, record_from_result


def _finding(sev: str) -> Finding:
    return Finding(
        id=sev,
        severity=sev,  # type: ignore[arg-type]
        category="security",
        file="a.py",
        line=1,
        title="t",
        explanation="e",
        recommendation="r",
        confidence="high",
        reviewer="security",
    )


def _record(**over: object) -> ReviewRecord:
    base: dict[str, object] = {
        "timestamp": "2026-05-29T00:00:00Z",
        "target": "main",
        "tier": "lite",
        "reviewers_run": ["code_quality"],
        "reviewers_skipped": [],
        "findings_total": 0,
        "findings_by_severity": {},
        "decision": "approved",
        "duration_s": 0.1,
        "tokens_in": 0,
        "tokens_out": 0,
    }
    base.update(over)
    return ReviewRecord(**base)  # type: ignore[arg-type]


def test_record_from_result_counts_by_severity() -> None:
    result = ReviewResult(
        findings=[_finding("warning"), _finding("warning"), _finding("critical")],
        decision=Decision.SIGNIFICANT_CONCERNS,
        summary="s",
    )
    rec = record_from_result(
        result,
        timestamp="t",
        target="main",
        tier="full",
        reviewers_run=["security", "code_quality"],
        reviewers_skipped=["release"],
        duration_s=1.5,
        tokens_in=1234,
        tokens_out=567,
    )
    assert rec.findings_total == 3
    assert rec.findings_by_severity == {"warning": 2, "critical": 1}
    assert rec.decision == "significant_concerns"
    assert rec.tier == "full"
    assert rec.reviewers_skipped == ["release"]
    assert rec.tokens_in == 1234
    assert rec.tokens_out == 567


def test_emit_appends_jsonl(tmp_path: Path) -> None:
    path = tmp_path / ".prism" / "telemetry.jsonl"
    assert emit(_record(decision="approved"), path) is True
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["decision"] == "approved"


def test_emit_appends_a_second_record(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    emit(_record(), path)
    emit(_record(), path)
    assert len(path.read_text().strip().splitlines()) == 2


def test_emit_is_fire_and_forget_never_raises(tmp_path: Path) -> None:
    blocker = tmp_path / "afile"
    blocker.write_text("x")  # a regular file
    bad = blocker / "telemetry.jsonl"  # parent is a file -> write must fail
    assert emit(_record(), bad) is False  # returns False, does NOT raise
