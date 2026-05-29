import json

import pytest

from prism.coordinator import CoordinatorOutputError, FanOutCoordinator
from prism.engines.base import Effort, ParsedResult
from prism.findings import Decision, Finding


class CaptureEngine:
    """Captures prompts and returns scripted texts."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.calls = 0
        self.prompts: list[str] = []

    def run(self, prompt: str, *, effort: Effort, model: str | None = None) -> ParsedResult:
        self.prompts.append(prompt)
        text = self._texts[min(self.calls, len(self._texts) - 1)]
        self.calls += 1
        return ParsedResult(text=text)


def _finding(fid: str = "f1", reviewer: str = "security") -> Finding:
    return Finding(
        id=fid,
        severity="warning",
        category="security",
        file="a.py",
        line=1,
        title="t",
        explanation="e",
        recommendation="r",
        confidence="high",
        reviewer=reviewer,
    )


def _verdict(decision: str, findings: list[dict[str, object]]) -> str:
    return json.dumps({"decision": decision, "summary": "s", "findings": findings})


def test_judge_parses_review_result() -> None:
    verdict = _verdict("approved_with_comments", [_finding().model_dump(mode="json")])
    engine = CaptureEngine([verdict])
    result = FanOutCoordinator().judge([_finding()], context="ctx", engine=engine)
    assert result.decision is Decision.APPROVED_WITH_COMMENTS
    assert len(result.findings) == 1


def test_judge_empty_is_approved() -> None:
    engine = CaptureEngine([_verdict("approved", [])])
    result = FanOutCoordinator().judge([], context="ctx", engine=engine)
    assert result.decision is Decision.APPROVED
    assert result.findings == []


def test_judge_feeds_input_findings_to_the_engine() -> None:
    engine = CaptureEngine([_verdict("approved", [])])
    FanOutCoordinator().judge([_finding(fid="UNIQUE-ID-123")], context="ctx", engine=engine)
    assert "UNIQUE-ID-123" in engine.prompts[0]


def test_judge_repair_retry_then_valid() -> None:
    engine = CaptureEngine(["not json", _verdict("approved", [])])
    result = FanOutCoordinator().judge([], context="ctx", engine=engine)
    assert result.decision is Decision.APPROVED
    assert engine.calls == 2


def test_judge_raises_after_two_failures() -> None:
    engine = CaptureEngine(["garbage", "still garbage"])
    with pytest.raises(CoordinatorOutputError):
        FanOutCoordinator().judge([], context="ctx", engine=engine)
