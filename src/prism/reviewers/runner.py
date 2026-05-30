"""Run one reviewer: build its prompt, call the engine, parse validated findings.

The model is asked for a JSON array of findings (see REVIEWER_SHARED.md). Output is
parsed and validated to ``Finding`` objects; on a parse/validation failure the reviewer
is asked once more for clean JSON before giving up.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from prism.config import ReviewerConfig
from prism.engines.base import Engine
from prism.findings import Finding
from prism.jsonio import extract_json_array, strip_code_fence
from prism.prompts import build_prompt
from prism.transcripts import write_transcript

_REPAIR_SUFFIX = (
    "\n\nYour previous reply was not valid JSON. "
    "Return ONLY the JSON array of findings, with no prose or code fences."
)


class ReviewerOutputError(RuntimeError):
    """A reviewer did not return valid findings JSON, even after one repair retry."""


def _parse_findings(text: str, reviewer_name: str) -> list[Finding] | None:
    """Parse a findings JSON array, tolerating JSON wrapped in prose; None if unparseable."""
    # Try the cleaned text first, then a best-effort extraction of the array from prose.
    for candidate in (strip_code_fence(text), extract_json_array(text)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list):
            continue
        findings: list[Finding] = []
        valid = True
        for item in data:
            if isinstance(item, dict):
                item.setdefault("reviewer", reviewer_name)
            try:
                findings.append(Finding.model_validate(item))
            except ValidationError:
                valid = False
                break
        if valid:
            return findings
    return None


def run_reviewer(
    name: str,
    reviewer: ReviewerConfig,
    engine: Engine,
    context: str,
    *,
    model: str | None = None,
    transcript_dir: Path | str | None = None,
) -> list[Finding]:
    """Build the prompt, run the engine, and return validated findings (one repair retry).

    When ``transcript_dir`` is set, each invocation's raw event stream is persisted to
    ``<transcript_dir>/<name>.jsonl`` for later inspection.
    """
    prompt = build_prompt(name, context)
    result = engine.run(prompt, effort=reviewer.effort, model=model)
    write_transcript(transcript_dir, name, result.raw)
    findings = _parse_findings(result.text, name)
    if findings is None:
        result = engine.run(prompt + _REPAIR_SUFFIX, effort=reviewer.effort, model=model)
        write_transcript(transcript_dir, name, result.raw)
        findings = _parse_findings(result.text, name)
        if findings is None:
            raise ReviewerOutputError(f"reviewer {name!r} returned invalid findings JSON")
    return findings
