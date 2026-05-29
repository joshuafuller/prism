"""Coordinator: run reviewers concurrently and (later) judge their findings.

Orchestration is a seam (ADR-0008). The MVP ships ``FanOutCoordinator``: deterministic
fan-out of reviewers as concurrent subprocess calls (one-shot CLIs, ADR-0007), with a
per-reviewer timeout. A reviewer that times out or errors is **skipped with a recorded
reason** — never silently dropped. The judge pass is added in a later task.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from pydantic import ValidationError

from prism.config import ReviewerConfig
from prism.engines.base import Effort, Engine
from prism.findings import Finding, ReviewResult
from prism.jsonio import strip_code_fence
from prism.prompts import build_prompt
from prism.reviewers.runner import run_reviewer

_JUDGE_REPAIR = (
    "\n\nYour previous reply was not valid JSON. Return ONLY the JSON object "
    '{"decision", "summary", "findings"} with no prose or code fences.'
)


class CoordinatorOutputError(RuntimeError):
    """The coordinator did not return a valid review JSON object after a repair retry."""


@dataclass(frozen=True, slots=True)
class ReviewerJob:
    name: str
    config: ReviewerConfig
    engine: Engine
    model: str | None = None


@dataclass(frozen=True, slots=True)
class FanOutResult:
    findings: list[Finding]
    skipped: list[tuple[str, str]]  # (reviewer name, reason)


class FanOutCoordinator:
    def __init__(self, *, per_reviewer_timeout: float = 300.0) -> None:
        self._timeout = per_reviewer_timeout

    def gather_findings(self, jobs: list[ReviewerJob], context: str) -> FanOutResult:
        """Run all reviewer jobs concurrently; aggregate findings, record skips."""
        return asyncio.run(self._gather(jobs, context))

    async def _gather(self, jobs: list[ReviewerJob], context: str) -> FanOutResult:
        async def run_one(job: ReviewerJob) -> list[Finding]:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    run_reviewer, job.name, job.config, job.engine, context, model=job.model
                ),
                timeout=self._timeout,
            )

        results = await asyncio.gather(*(run_one(job) for job in jobs), return_exceptions=True)

        findings: list[Finding] = []
        skipped: list[tuple[str, str]] = []
        for job, result in zip(jobs, results, strict=True):
            if isinstance(result, TimeoutError):
                skipped.append((job.name, f"timed out after {self._timeout}s"))
            elif isinstance(result, BaseException):
                skipped.append((job.name, f"{type(result).__name__}: {result}"))
            else:
                findings.extend(result)
        return FanOutResult(findings=findings, skipped=skipped)

    def judge(
        self,
        findings: list[Finding],
        context: str,
        *,
        engine: Engine,
        effort: Effort = Effort.HIGH,
        model: str | None = None,
    ) -> ReviewResult:
        """Have the coordinator engine dedup/filter the findings and decide an outcome."""
        prompt = self._judge_prompt(context, findings)
        result = engine.run(prompt, effort=effort, model=model)
        parsed = _parse_review_result(result.text)
        if parsed is None:
            result = engine.run(prompt + _JUDGE_REPAIR, effort=effort, model=model)
            parsed = _parse_review_result(result.text)
            if parsed is None:
                raise CoordinatorOutputError("coordinator returned invalid review JSON")
        return parsed

    @staticmethod
    def _judge_prompt(context: str, findings: list[Finding]) -> str:
        findings_json = json.dumps([f.model_dump(mode="json") for f in findings], indent=2)
        augmented = f"{context}\n\nReviewer findings to judge (JSON):\n{findings_json}"
        return build_prompt("coordinator", augmented)


def _parse_review_result(text: str) -> ReviewResult | None:
    try:
        obj = json.loads(strip_code_fence(text))
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    try:
        return ReviewResult.model_validate(obj)
    except ValidationError:
        return None
