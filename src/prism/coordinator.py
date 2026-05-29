"""Coordinator: run reviewers concurrently and (later) judge their findings.

Orchestration is a seam (ADR-0008). The MVP ships ``FanOutCoordinator``: deterministic
fan-out of reviewers as concurrent subprocess calls (one-shot CLIs, ADR-0007), with a
per-reviewer timeout. A reviewer that times out or errors is **skipped with a recorded
reason** — never silently dropped. The judge pass is added in a later task.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from prism.config import ReviewerConfig
from prism.engines.base import Engine
from prism.findings import Finding
from prism.reviewers.runner import run_reviewer


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
