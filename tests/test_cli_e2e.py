import json
import subprocess
from pathlib import Path

import pytest

from prism import cli
from prism.config import load_config
from prism.engines.base import Effort, ParsedResult
from prism.findings import Decision, ReviewResult

EXAMPLE = Path(__file__).resolve().parent.parent / "prism.example.yaml"


class ScriptedEngine:
    """Dispatches on prompt: coordinator -> verdict JSON, reviewer -> empty findings."""

    def run(self, prompt: str, *, effort: Effort, model: str | None = None) -> ParsedResult:
        if "Review Coordinator" in prompt:
            verdict = {
                "decision": "approved_with_comments",
                "summary": "Looks fine.",
                "findings": [],
            }
            return ParsedResult(text=json.dumps(verdict))
        return ParsedResult(text="[]")


class FailingEngine:
    """Always returns unparseable output -> reviewer fails and is skipped."""

    def run(self, prompt: str, *, effort: Effort, model: str | None = None) -> ParsedResult:
        return ParsedResult(text="not valid json")


class RecordingEngine:
    """Returns empty findings and counts how many times it was called."""

    def __init__(self) -> None:
        self.calls = 0

    def run(self, prompt: str, *, effort: Effort, model: str | None = None) -> ParsedResult:
        self.calls += 1
        return ParsedResult(text="[]")


class FakeProvider:
    def __init__(self) -> None:
        self.posted: tuple[int, str] | None = None

    def auth_account(self) -> str:
        return "joshuafuller"

    def post_summary(self, pr: int, body: str) -> None:
        self.posted = (pr, body)


def _repo_with_change(repo: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)

    git("checkout", "-q", "-b", "feature")
    (repo / "a.py").write_text("x = 2\n")
    git("add", "-A")
    git("commit", "-q", "-m", "change")


def test_run_local_review_end_to_end(git_repo: Path) -> None:
    _repo_with_change(git_repo)
    engine = ScriptedEngine()
    provider = FakeProvider()
    result = cli.run_local_review(
        load_config(EXAMPLE),
        target="main",
        repo=git_repo,
        engines={"claude-cli": engine, "codex-cli": engine},
        provider=provider,
        post_pr=42,
    )
    assert isinstance(result, ReviewResult)
    assert result.decision is Decision.APPROVED_WITH_COMMENTS
    assert (git_repo / ".prism" / "report.md").read_text().count("Prism review") == 1
    assert json.loads((git_repo / ".prism" / "findings.json").read_text()) == []
    assert provider.posted is not None and provider.posted[0] == 42


def test_run_local_review_surfaces_skipped_reviewer(git_repo: Path) -> None:
    _repo_with_change(git_repo)
    # security -> codex-cli (fails), code_quality + coordinator -> claude-cli (scripted)
    engines = {"claude-cli": ScriptedEngine(), "codex-cli": FailingEngine()}
    cli.run_local_review(load_config(EXAMPLE), target="main", repo=git_repo, engines=engines)
    report = (git_repo / ".prism" / "report.md").read_text()
    assert "Reviewers skipped" in report
    assert "security" in report


def test_trivial_diff_skips_higher_tier_reviewers(git_repo: Path, tmp_path: Path) -> None:
    _repo_with_change(git_repo)  # 1-line change -> trivial tier
    cfg = tmp_path / "prism.yaml"
    cfg.write_text(
        "engines:\n  claude-cli: {kind: claude-cli}\n  codex-cli: {kind: codex-cli}\n"
        "reviewers:\n"
        "  code_quality: {engine: claude-cli, effort: medium}\n"
        "  security: {engine: codex-cli, effort: high, min_tier: full}\n"
        "coordinator: {engine: claude-cli, effort: high}\n"
    )
    security = RecordingEngine()
    engines = {"claude-cli": ScriptedEngine(), "codex-cli": security}
    cli.run_local_review(load_config(cfg), target="main", repo=git_repo, engines=engines)

    assert security.calls == 0  # security requires 'full'; diff is 'trivial'
    report = (git_repo / ".prism" / "report.md").read_text()
    assert "security" in report  # reported, not silently dropped (ADR-0012/0013)


def test_run_local_review_emits_telemetry(git_repo: Path) -> None:
    _repo_with_change(git_repo)
    engine = ScriptedEngine()
    cli.run_local_review(
        load_config(EXAMPLE),
        target="main",
        repo=git_repo,
        engines={"claude-cli": engine, "codex-cli": engine},
    )
    tel = git_repo / ".prism" / "telemetry.jsonl"
    record = json.loads(tel.read_text().strip().splitlines()[-1])
    assert "tier" in record
    assert record["decision"] in {
        "approved",
        "approved_with_comments",
        "minor_issues",
        "significant_concerns",
    }


def test_ast_risk_escalates_a_tiny_dangerous_diff(git_repo: Path, tmp_path: Path) -> None:
    # A tiny diff (trivial by size) that introduces eval() must escalate to full so the
    # full-tier security reviewer runs. The eval string below is a fixture, never executed.
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(git_repo), *args], check=True, capture_output=True, text=True
        )

    git("checkout", "-q", "-b", "feature")
    (git_repo / "a.py").write_text("import sys\nv = eval(sys.argv[1])\n")
    git("add", "-A")
    git("commit", "-q", "-m", "tiny but risky")

    cfg = tmp_path / "prism.yaml"
    cfg.write_text(
        "engines:\n  claude-cli: {kind: claude-cli}\n  codex-cli: {kind: codex-cli}\n"
        "reviewers:\n"
        "  code_quality: {engine: claude-cli, effort: medium}\n"
        "  security: {engine: codex-cli, effort: high, min_tier: full}\n"
        "coordinator: {engine: claude-cli, effort: high}\n"
    )
    security = RecordingEngine()
    cli.run_local_review(
        load_config(cfg),
        target="main",
        repo=git_repo,
        engines={"claude-cli": ScriptedEngine(), "codex-cli": security},
    )
    assert security.calls >= 1  # AST escalated trivial->full, so security ran


def test_telemetry_excludes_failed_reviewer_from_run(git_repo: Path) -> None:
    _repo_with_change(git_repo)  # trivial diff -> all default-tier reviewers run
    engines = {"claude-cli": ScriptedEngine(), "codex-cli": FailingEngine()}  # security fails
    cli.run_local_review(load_config(EXAMPLE), target="main", repo=git_repo, engines=engines)
    rec = json.loads((git_repo / ".prism" / "telemetry.jsonl").read_text().strip().splitlines()[-1])
    assert "security" in rec["reviewers_skipped"]
    assert "security" not in rec["reviewers_run"]  # failed -> not counted as run


def test_telemetry_path_param_override(git_repo: Path, tmp_path: Path) -> None:
    _repo_with_change(git_repo)
    out = tmp_path / "global" / "telemetry.jsonl"
    engine = ScriptedEngine()
    cli.run_local_review(
        load_config(EXAMPLE),
        target="main",
        repo=git_repo,
        engines={"claude-cli": engine, "codex-cli": engine},
        telemetry_path=out,
    )
    assert out.exists()
    assert "decision" in json.loads(out.read_text().strip().splitlines()[-1])


def test_telemetry_path_from_env(git_repo: Path, tmp_path: Path, monkeypatch) -> None:
    _repo_with_change(git_repo)
    out = tmp_path / "env-telemetry.jsonl"
    monkeypatch.setenv("PRISM_TELEMETRY_PATH", str(out))
    engine = ScriptedEngine()
    cli.run_local_review(
        load_config(EXAMPLE),
        target="main",
        repo=git_repo,
        engines={"claude-cli": engine, "codex-cli": engine},
    )
    assert out.exists()


def test_missing_reviewer_prompt_fails_loudly(git_repo: Path, tmp_path: Path) -> None:
    _repo_with_change(git_repo)
    cfg = tmp_path / "prism.yaml"
    cfg.write_text(
        "engines:\n  claude-cli: {kind: claude-cli}\n"
        "reviewers:\n  ghost: {engine: claude-cli}\n"
        "coordinator: {engine: claude-cli}\n"
    )
    with pytest.raises(ValueError, match="ghost"):
        cli.run_local_review(
            load_config(cfg), target="main", repo=git_repo, engines={"claude-cli": ScriptedEngine()}
        )


def test_main_exits_1_on_significant_concerns(monkeypatch) -> None:
    blocked = ReviewResult(findings=[], decision=Decision.SIGNIFICANT_CONCERNS, summary="bad")
    monkeypatch.setattr(cli, "run_local_review", lambda *a, **k: blocked)
    code = cli.main(["local", "--target", "main", "--config", str(EXAMPLE), "--repo", "."])
    assert code == 1


def test_main_exits_0_on_approved(monkeypatch) -> None:
    ok = ReviewResult(findings=[], decision=Decision.APPROVED, summary="ok")
    monkeypatch.setattr(cli, "run_local_review", lambda *a, **k: ok)
    code = cli.main(["local", "--target", "main", "--config", str(EXAMPLE), "--repo", "."])
    assert code == 0


def test_main_fails_when_decision_more_severe_than_fail_on(monkeypatch, tmp_path) -> None:
    cfg = tmp_path / "prism.yaml"
    cfg.write_text(
        "engines:\n  claude-cli: {kind: claude-cli}\n"
        "reviewers:\n  code_quality: {engine: claude-cli, effort: low}\n"
        "coordinator: {engine: claude-cli, effort: low}\n"
        "policy:\n  fail_on: minor_issues\n"
    )
    blocked = ReviewResult(findings=[], decision=Decision.SIGNIFICANT_CONCERNS, summary="x")
    monkeypatch.setattr(cli, "run_local_review", lambda *a, **k: blocked)
    assert cli.main(["local", "--target", "main", "--config", str(cfg), "--repo", "."]) == 1
