import json
import threading
import time

from prism.config import ReviewerConfig
from prism.coordinator import FanOutCoordinator, ReviewerJob
from prism.engines.base import Effort, ParsedResult


class ScriptedEngine:
    """Returns a fixed findings JSON; optionally sleeps to simulate slow work."""

    def __init__(self, text: str, *, sleep: float = 0.0, probe: "Probe | None" = None) -> None:
        self._text = text
        self._sleep = sleep
        self._probe = probe

    def run(self, prompt: str, *, effort: Effort, model: str | None = None) -> ParsedResult:
        if self._probe is not None:
            self._probe.enter()
        if self._sleep:
            time.sleep(self._sleep)
        if self._probe is not None:
            self._probe.leave()
        return ParsedResult(text=self._text)


class Probe:
    """Tracks the max number of reviewers running at once."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def enter(self) -> None:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)

    def leave(self) -> None:
        with self._lock:
            self.active -= 1


def _finding(reviewer: str) -> str:
    return json.dumps(
        [
            {
                "id": reviewer,
                "severity": "warning",
                "category": "security",
                "file": "a.py",
                "line": 1,
                "title": "t",
                "explanation": "e",
                "recommendation": "r",
                "confidence": "high",
                "reviewer": reviewer,
            }
        ]
    )


_CFG = ReviewerConfig(engine="x", effort=Effort.HIGH)


def test_aggregates_findings_from_all_reviewers() -> None:
    jobs = [
        ReviewerJob("security", _CFG, ScriptedEngine(_finding("security"))),
        ReviewerJob("code_quality", _CFG, ScriptedEngine(_finding("code_quality"))),
    ]
    result = FanOutCoordinator().gather_findings(jobs, context="ctx")
    assert {f.reviewer for f in result.findings} == {"security", "code_quality"}
    assert result.skipped == []


def test_reviewers_run_concurrently() -> None:
    # Names must have a matching agents/<name>.md (build_prompt reads it).
    probe = Probe()
    jobs = [
        ReviewerJob("security", _CFG, ScriptedEngine("[]", probe=probe)),
        ReviewerJob("code_quality", _CFG, ScriptedEngine("[]", probe=probe)),
    ]
    FanOutCoordinator().gather_findings(jobs, context="ctx")
    assert probe.max_active >= 2  # they overlapped


def test_timed_out_reviewer_is_skipped_others_return() -> None:
    jobs = [
        ReviewerJob("security", _CFG, ScriptedEngine("[]", sleep=0.5)),
        ReviewerJob("code_quality", _CFG, ScriptedEngine(_finding("code_quality"))),
    ]
    result = FanOutCoordinator(per_reviewer_timeout=0.05).gather_findings(jobs, context="ctx")
    assert [f.reviewer for f in result.findings] == ["code_quality"]
    assert [name for name, _ in result.skipped] == ["security"]


def test_failing_reviewer_is_skipped_others_return() -> None:
    jobs = [
        ReviewerJob("security", _CFG, ScriptedEngine("not valid json")),
        ReviewerJob("code_quality", _CFG, ScriptedEngine(_finding("code_quality"))),
    ]
    result = FanOutCoordinator().gather_findings(jobs, context="ctx")
    assert [f.reviewer for f in result.findings] == ["code_quality"]
    assert "security" in [name for name, _ in result.skipped]
