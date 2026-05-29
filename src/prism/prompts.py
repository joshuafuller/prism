"""Build reviewer/coordinator prompts from markdown + sanitize untrusted context.

A prompt = shared rules (`REVIEWER_SHARED.md`) + the agent's own markdown + the
(sanitized) shared context. Adding or tuning a reviewer is editing markdown under
``agents/`` — no core code change (ADR-0009). User-controlled context is sanitized of
prompt-boundary tags before insertion (prompt-injection defense).
"""

from __future__ import annotations

import re
from pathlib import Path

AGENTS_DIR = Path(__file__).parent / "agents"

# The specialist reviewers Prism spawns (the coordinator is separate).
REVIEWER_NAMES = ("security", "code_quality")

# XML-style section tags an attacker might inject to break out of the prompt structure.
PROMPT_BOUNDARY_TAGS = (
    "mr_input",
    "mr_body",
    "mr_comments",
    "mr_details",
    "changed_files",
    "existing_inline_findings",
    "previous_review",
    "custom_review_instructions",
    "agents_md_template_instructions",
    "context",
)
_BOUNDARY_RE = re.compile(
    r"</?(?:" + "|".join(PROMPT_BOUNDARY_TAGS) + r")\b[^>]*>",
    re.IGNORECASE,
)


def sanitize_context(text: str) -> str:
    """Strip prompt-boundary tags from untrusted context, keeping the inner text."""
    return _BOUNDARY_RE.sub("", text)


def _read_markdown(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text()


def build_prompt(reviewer: str, context: str) -> str:
    """Assemble a full prompt: shared rules + the agent's markdown + sanitized context."""
    shared = _read_markdown("REVIEWER_SHARED")
    agent = _read_markdown(reviewer)
    safe_context = sanitize_context(context)
    return f"{shared}\n\n{agent}\n\n<context>\n{safe_context}\n</context>\n"
