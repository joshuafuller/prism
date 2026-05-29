"""Helpers for parsing JSON that LLMs sometimes wrap in markdown code fences."""

from __future__ import annotations

import re

_FENCE_OPEN = re.compile(r"^```[a-zA-Z0-9]*\n")
_FENCE_CLOSE = re.compile(r"\n```$")


def strip_code_fence(text: str) -> str:
    """Remove a leading ```lang fence and trailing ``` fence, if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _FENCE_OPEN.sub("", stripped)
        stripped = _FENCE_CLOSE.sub("", stripped.strip())
    return stripped.strip()
