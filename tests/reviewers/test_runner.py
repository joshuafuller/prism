import json

import pytest

from prism.config import ReviewerConfig
from prism.engines.base import Effort, ParsedResult
from prism.findings import Severity
from prism.reviewers.runner import ReviewerOutputError, run_reviewer


class FakeEngine:
    """Duck-typed engine returning scripted texts (no real model)."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.calls = 0

    def run(self, prompt: str, *, effort: Effort, model: str | None = None) -> ParsedResult:
        text = self._texts[min(self.calls, len(self._texts) - 1)]
        self.calls += 1
        return ParsedResult(text=text)


_CFG = ReviewerConfig(engine="codex-cli", effort=Effort.HIGH)


def _finding_json(**over: object) -> str:
    item = {
        "id": "1",
        "severity": "warning",
        "category": "security",
        "file": "a.py",
        "line": 3,
        "title": "t",
        "explanation": "e",
        "recommendation": "r",
        "confidence": "high",
        "reviewer": "security",
    }
    item.update(over)
    return json.dumps([item])


def test_parses_valid_findings() -> None:
    eng = FakeEngine([_finding_json()])
    findings = run_reviewer("security", _CFG, eng, context="ctx")
    assert len(findings) == 1
    assert findings[0].severity is Severity.WARNING


def test_handles_code_fenced_json() -> None:
    eng = FakeEngine(["```json\n[]\n```"])
    assert run_reviewer("security", _CFG, eng, context="ctx") == []


def test_empty_array_is_no_findings() -> None:
    eng = FakeEngine(["[]"])
    assert run_reviewer("security", _CFG, eng, context="ctx") == []


def test_repair_retry_on_malformed_then_valid() -> None:
    eng = FakeEngine(["not json at all", "[]"])
    findings = run_reviewer("security", _CFG, eng, context="ctx")
    assert findings == []
    assert eng.calls == 2  # one repair retry


def test_raises_after_two_failures() -> None:
    eng = FakeEngine(["garbage", "still garbage"])
    with pytest.raises(ReviewerOutputError):
        run_reviewer("security", _CFG, eng, context="ctx")


def test_fills_reviewer_name_when_missing() -> None:
    item = json.loads(_finding_json())
    del item[0]["reviewer"]
    eng = FakeEngine([json.dumps(item)])
    findings = run_reviewer("security", _CFG, eng, context="ctx")
    assert findings[0].reviewer == "security"
