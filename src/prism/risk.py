"""Risk-tier classification: scale reviewers/effort by the size and nature of a diff.

See ADR-0013. Security-sensitive paths always force a full review.
"""

from __future__ import annotations

import re
from enum import StrEnum

from prism.diff.source import ChangedFile

_SECURITY_PATTERNS = re.compile(
    r"(^|/)(auth|oauth|jwt|crypto|rbac|permissions|middleware)(/|$)"
    r"|(^|/)\.github/workflows/"
    r"|(^|/)\.gitlab-ci\.yml$"
    r"|(^|/)Dockerfile$"
    r"|(^|/)(helm|k8s|terraform|tofu|deployment)(/|$)",
    re.IGNORECASE,
)


class RiskTier(StrEnum):
    TRIVIAL = "trivial"
    LITE = "lite"
    FULL = "full"

    @property
    def rank(self) -> int:
        return _TIER_RANK[self]


_TIER_RANK = {RiskTier.TRIVIAL: 0, RiskTier.LITE: 1, RiskTier.FULL: 2}


def is_security_sensitive(path: str) -> bool:
    return _SECURITY_PATTERNS.search(path) is not None


def assess_risk_tier(files: list[ChangedFile]) -> RiskTier:
    total_lines = sum(f.added + f.removed for f in files)
    file_count = len(files)
    if file_count > 50 or any(is_security_sensitive(f.path) for f in files):
        return RiskTier.FULL
    if total_lines <= 10 and file_count <= 20:
        return RiskTier.TRIVIAL
    if total_lines <= 100 and file_count <= 20:
        return RiskTier.LITE
    return RiskTier.FULL
