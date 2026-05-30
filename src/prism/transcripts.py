"""Persist the raw CLI event stream of a single engine invocation (fire-and-forget).

The engines emit JSONL while reviewing (assistant/tool_use/result events). We keep that
stream per run under ``.prism/runs/<label>.jsonl`` so a review can be inspected after the
fact — what the model thought, and crucially whether it used its ``Read``/``Grep`` tools
to verify against the source (the article's coordinator behavior). JSONL means every line
is independently valid, so even a stream cut short by an early exit is still useful.

Like telemetry, this must never break a review: ``write_transcript`` swallows all errors.
"""

from __future__ import annotations

from pathlib import Path


def write_transcript(run_dir: Path | str | None, label: str, raw: str) -> None:
    """Append ``raw`` to ``<run_dir>/<label>.jsonl``. No-op if disabled or empty; never raises."""
    if run_dir is None or not raw:
        return
    try:
        target = Path(run_dir)
        target.mkdir(parents=True, exist_ok=True)
        with (target / f"{label}.jsonl").open("a", encoding="utf-8") as handle:
            # Terminate each append so a stream without a trailing newline can't fuse its
            # last JSON object onto the next append's first line (keeps every line valid).
            handle.write(raw if raw.endswith("\n") else raw + "\n")
    except Exception:
        pass
