"""The ``prism`` command — local-mode review wiring all the pieces together.

    prism local --target main [--config prism.yaml] [--repo .] [--post-pr N]

Flow: git diff -> filter noise -> build .prism/ workspace -> run reviewers concurrently
-> coordinator judge pass -> markdown report (+ optional GitHub PR comment). Exit code is
nonzero only when the decision matches the configured policy (default: significant_concerns).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from prism.ast_risk import ast_risk_labels
from prism.config import Config, load_config
from prism.coordinator import FanOutCoordinator, ReviewerJob
from prism.diff.filter import FilterResult, filter_diff
from prism.diff.source import GitDiffSource
from prism.engines.base import Effort, Engine
from prism.engines.registry import build_engines
from prism.findings import ReviewResult
from prism.reporter import to_markdown
from prism.risk import RiskTier, assess_risk_tier
from prism.telemetry import emit, record_from_result
from prism.vcs.base import VCSProvider
from prism.vcs.github import GitHubProvider
from prism.workspace import build_workspace


def _build_context(target: str, filtered: FilterResult, risk_signals: list[str]) -> str:
    lines = [f"Reviewing changes against target: {target}", "", "## Changed files"]
    lines += [f"- {f.path} (+{f.added}/-{f.removed})" for f in filtered.kept]
    if risk_signals:
        lines.append("")
        lines.append("## Risk signals (AST)")
        lines += [f"- {s}" for s in risk_signals]
    if filtered.skipped:
        lines.append("")
        lines.append("## Skipped (noise)")
        lines += [f"- {path}: {reason}" for path, reason in filtered.skipped]
    lines.append("")
    lines.append("## Patches")
    for f in filtered.kept:
        lines.append(f"\n### {f.path}\n```diff\n{f.patch}\n```")
    return "\n".join(lines)


def _ast_risk_signals(filtered: FilterResult, repo: Path | str) -> list[str]:
    """Risky constructs the diff introduced in changed Python files (ADR-0014)."""
    signals: list[str] = []
    for f in filtered.kept:
        if not f.path.endswith(".py"):
            continue
        try:
            new_source = (Path(repo) / f.path).read_text(encoding="utf-8")
        except OSError:
            continue
        for label in ast_risk_labels(new_source, f.patch):
            signals.append(f"{f.path}: introduces {label}")
    return signals


def run_local_review(
    config: Config,
    target: str,
    repo: Path | str = ".",
    *,
    engines: dict[str, Engine] | None = None,
    provider: VCSProvider | None = None,
    post_pr: int | None = None,
    telemetry_path: Path | str | None = None,
) -> ReviewResult:
    """Run a full local review and return the judged result (engines injectable for tests)."""
    start = time.perf_counter()
    engines = engines or build_engines(config)
    filtered = filter_diff(GitDiffSource(target, repo).changed_files())

    # Risk tier selects which reviewers run and the coordinator's effort (ADR-0013).
    # An AST risk signal escalates to full even on a tiny diff (ADR-0014).
    tier = assess_risk_tier(filtered.kept)
    risk_signals = _ast_risk_signals(filtered, repo)
    if risk_signals:
        tier = RiskTier.FULL

    context = _build_context(target, filtered, risk_signals)
    build_workspace(filtered.kept, context, repo)
    jobs: list[ReviewerJob] = []
    tier_skipped: list[tuple[str, str]] = []
    for name, rc in config.reviewers.items():
        if tier.rank >= rc.min_tier.rank:
            jobs.append(ReviewerJob(name, rc, engines[rc.engine], config.engines[rc.engine].model))
        else:
            reason = f"not run: requires '{rc.min_tier}' tier (diff is '{tier}')"
            tier_skipped.append((name, reason))

    coordinator = FanOutCoordinator()
    fanout = coordinator.gather_findings(jobs, context)
    skipped = tier_skipped + fanout.skipped
    failed_names = {name for name, _ in fanout.skipped}
    reviewers_run = [job.name for job in jobs if job.name not in failed_names]

    # Surface skipped reviewers to the coordinator too, so an incomplete review is judged
    # as incomplete rather than silently treated as clean (ADR-0012: no silent truncation).
    judge_context = context
    if skipped:
        notes = "\n".join(f"- {name}: {reason}" for name, reason in skipped)
        judge_context = f"{context}\n\n## Reviewers not run / incomplete\n{notes}"

    coord_engine = engines[config.coordinator.engine]
    coord_model = config.engines[config.coordinator.engine].model
    coord_effort = Effort.LOW if tier is RiskTier.TRIVIAL else config.coordinator.effort
    result = coordinator.judge(
        fanout.findings,
        judge_context,
        engine=coord_engine,
        effort=coord_effort,
        model=coord_model,
    )

    report = to_markdown(result, skipped=skipped)
    prism_dir = Path(repo) / ".prism"
    prism_dir.mkdir(parents=True, exist_ok=True)
    (prism_dir / "report.md").write_text(report)
    (prism_dir / "findings.json").write_text(
        json.dumps([f.model_dump(mode="json") for f in result.findings], indent=2)
    )

    # Fire-and-forget telemetry (never breaks the review). Path precedence:
    # explicit arg > PRISM_TELEMETRY_PATH env (for a global, accumulating log) > repo .prism/.
    tel_path = (
        telemetry_path or os.environ.get("PRISM_TELEMETRY_PATH") or prism_dir / "telemetry.jsonl"
    )
    emit(
        record_from_result(
            result,
            timestamp=datetime.now(UTC).isoformat(),
            target=target,
            tier=tier.value,
            reviewers_run=reviewers_run,
            reviewers_skipped=[name for name, _ in skipped],
            duration_s=time.perf_counter() - start,
        ),
        tel_path,
    )

    if post_pr is not None:
        prov = provider or GitHubProvider()
        prov.auth_account()  # identity precheck (raises if gh isn't authed)
        prov.post_summary(post_pr, report)

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prism", description="AI code review on your subscriptions"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    local = sub.add_parser("local", help="review local changes against a target ref")
    local.add_argument("--target", required=True, help="git ref to diff against (e.g. main)")
    local.add_argument("--config", default="prism.yaml", help="path to prism config")
    local.add_argument("--repo", default=".", help="repo working tree")
    local.add_argument("--post-pr", type=int, default=None, help="also post summary to this PR")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    result = run_local_review(config, args.target, args.repo, post_pr=args.post_pr)
    print(to_markdown(result))
    # Fail CI when the decision is at least as severe as the configured threshold (ADR-0011).
    return 1 if result.decision.at_least(config.policy.fail_on) else 0
