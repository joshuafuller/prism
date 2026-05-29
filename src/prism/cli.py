"""The ``prism`` command — local-mode review wiring all the pieces together.

    prism local --target main [--config prism.yaml] [--repo .] [--post-pr N]

Flow: git diff -> filter noise -> build .prism/ workspace -> run reviewers concurrently
-> coordinator judge pass -> markdown report (+ optional GitHub PR comment). Exit code is
nonzero only when the decision matches the configured policy (default: significant_concerns).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prism.config import Config, load_config
from prism.coordinator import FanOutCoordinator, ReviewerJob
from prism.diff.filter import FilterResult, filter_diff
from prism.diff.source import GitDiffSource
from prism.engines.base import Engine
from prism.engines.registry import build_engines
from prism.findings import ReviewResult
from prism.reporter import to_markdown
from prism.vcs.base import VCSProvider
from prism.vcs.github import GitHubProvider
from prism.workspace import build_workspace


def _build_context(target: str, filtered: FilterResult) -> str:
    lines = [f"Reviewing changes against target: {target}", "", "## Changed files"]
    lines += [f"- {f.path} (+{f.added}/-{f.removed})" for f in filtered.kept]
    if filtered.skipped:
        lines.append("")
        lines.append("## Skipped (noise)")
        lines += [f"- {path}: {reason}" for path, reason in filtered.skipped]
    lines.append("")
    lines.append("## Patches")
    for f in filtered.kept:
        lines.append(f"\n### {f.path}\n```diff\n{f.patch}\n```")
    return "\n".join(lines)


def run_local_review(
    config: Config,
    target: str,
    repo: Path | str = ".",
    *,
    engines: dict[str, Engine] | None = None,
    provider: VCSProvider | None = None,
    post_pr: int | None = None,
) -> ReviewResult:
    """Run a full local review and return the judged result (engines injectable for tests)."""
    engines = engines or build_engines(config)
    filtered = filter_diff(GitDiffSource(target, repo).changed_files())
    context = _build_context(target, filtered)
    build_workspace(filtered.kept, context, repo)

    jobs = [
        ReviewerJob(name, rc, engines[rc.engine], config.engines[rc.engine].model)
        for name, rc in config.reviewers.items()
    ]
    coordinator = FanOutCoordinator()
    fanout = coordinator.gather_findings(jobs, context)

    # Surface skipped reviewers to the coordinator too, so an incomplete review is judged
    # as incomplete rather than silently treated as clean (ADR-0012: no silent truncation).
    judge_context = context
    if fanout.skipped:
        notes = "\n".join(f"- {name}: {reason}" for name, reason in fanout.skipped)
        judge_context = f"{context}\n\n## Reviewers that did not complete\n{notes}"

    coord_engine = engines[config.coordinator.engine]
    coord_model = config.engines[config.coordinator.engine].model
    result = coordinator.judge(
        fanout.findings,
        judge_context,
        engine=coord_engine,
        effort=config.coordinator.effort,
        model=coord_model,
    )

    report = to_markdown(result, skipped=fanout.skipped)
    prism_dir = Path(repo) / ".prism"
    prism_dir.mkdir(parents=True, exist_ok=True)
    (prism_dir / "report.md").write_text(report)
    (prism_dir / "findings.json").write_text(
        json.dumps([f.model_dump(mode="json") for f in result.findings], indent=2)
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
