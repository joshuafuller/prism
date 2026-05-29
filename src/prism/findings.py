"""Structured review findings and the coordinator's overall decision.

Reviewers return ``Finding`` objects (never free-form text); the coordinator's judge
pass aggregates them into a ``ReviewResult`` with one ``Decision``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

# Controlled vocabularies. Category/Confidence are simple literals (the judge may
# recategorize); Severity/Decision are enums because they carry behavior/ordering.
Category = Literal[
    "security",
    "code_quality",
    "performance",
    "documentation",
    "release",
    "other",
]
Confidence = Literal["high", "medium", "low"]


class Severity(StrEnum):
    """How serious a single finding is."""

    CRITICAL = "critical"  # exploitable, or will cause an outage / data loss
    WARNING = "warning"  # concrete bug or measurable regression
    SUGGESTION = "suggestion"  # improvement; never blocks by default


class Decision(StrEnum):
    """The coordinator's single overall verdict for a review."""

    APPROVED = "approved"
    APPROVED_WITH_COMMENTS = "approved_with_comments"
    MINOR_ISSUES = "minor_issues"
    SIGNIFICANT_CONCERNS = "significant_concerns"

    @property
    def rank(self) -> int:
        """Severity rank for ordering (approved=0 … significant_concerns=3)."""
        return _DECISION_RANK[self]

    def at_least(self, other: Decision) -> bool:
        """True if this decision is at least as severe as ``other`` (ADR-0011)."""
        return self.rank >= other.rank

    @property
    def blocks(self) -> bool:
        """Whether this decision should block the merge (fail CI)."""
        return self is Decision.SIGNIFICANT_CONCERNS


_DECISION_RANK = {
    Decision.APPROVED: 0,
    Decision.APPROVED_WITH_COMMENTS: 1,
    Decision.MINOR_ISSUES: 2,
    Decision.SIGNIFICANT_CONCERNS: 3,
}


class Finding(BaseModel):
    """A single, structured review finding."""

    id: str
    severity: Severity
    category: Category
    file: str
    line: int
    title: str
    explanation: str
    recommendation: str
    confidence: Confidence
    reviewer: str


class ReviewResult(BaseModel):
    """The aggregated, judged output of a whole review."""

    findings: list[Finding]
    decision: Decision
    summary: str
