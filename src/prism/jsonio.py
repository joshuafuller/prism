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


def _extract(text: str, open_ch: str, close_ch: str) -> str | None:
    s = strip_code_fence(text)
    start, end = s.find(open_ch), s.rfind(close_ch)
    if 0 <= start < end:
        return s[start : end + 1]
    return None


def extract_json_array(text: str) -> str | None:
    """Best-effort: the outermost ``[...]`` in text (handles JSON wrapped in prose)."""
    return _extract(text, "[", "]")


def extract_json_object(text: str) -> str | None:
    """Best-effort: the outermost ``{...}`` in text (handles JSON wrapped in prose)."""
    return _extract(text, "{", "}")
