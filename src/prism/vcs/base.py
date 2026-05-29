"""The VCS provider seam: read context and post review results to a PR/MR.

Prism's core depends only on this Protocol, never on GitHub/GitLab specifics, so a new
provider is a drop-in (ADR-0004). MVP ships GitHub via the `gh` CLI; GitLab is later.
"""

from __future__ import annotations

from typing import Protocol


class VCSProvider(Protocol):
    def auth_account(self) -> str:
        """Return the authenticated account login (for a pre-post identity check)."""
        ...

    def post_summary(self, pr: int, body: str) -> None:
        """Post a summary review comment to the given PR/MR."""
        ...
