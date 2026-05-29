"""Fire-and-forget per-review telemetry (local JSONL).

Telemetry must never break a review: ``emit`` swallows all errors and returns a bool.
Records capture the "show me the numbers" basics — tier, reviewers run/skipped, findings
by severity, decision, and duration. (Token usage is a tracked follow-up.)
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from prism.findings import ReviewResult


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    timestamp: str
    target: str
    tier: str
    reviewers_run: list[str]
    reviewers_skipped: list[str]
    findings_total: int
    findings_by_severity: dict[str, int]
    decision: str
    duration_s: float
    tokens_in: int
    tokens_out: int


def record_from_result(
    result: ReviewResult,
    *,
    timestamp: str,
    target: str,
    tier: str,
    reviewers_run: list[str],
    reviewers_skipped: list[str],
    duration_s: float,
    tokens_in: int = 0,
    tokens_out: int = 0,
) -> ReviewRecord:
    by_severity = Counter(f.severity.value for f in result.findings)
    return ReviewRecord(
        timestamp=timestamp,
        target=target,
        tier=tier,
        reviewers_run=list(reviewers_run),
        reviewers_skipped=list(reviewers_skipped),
        findings_total=len(result.findings),
        findings_by_severity=dict(by_severity),
        decision=result.decision.value,
        duration_s=duration_s,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def emit(record: ReviewRecord, path: Path | str) -> bool:
    """Append a record as one JSONL line. Never raises; returns success."""
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record)) + "\n")
        return True
    except Exception:
        return False
