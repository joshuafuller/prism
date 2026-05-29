"""Live end-to-end pipeline test (excluded from the default suite).

Run with: uv run pytest -m live
Builds a repo with a planted hardcoded secret, runs the full review against the real
subscription CLIs, and asserts the pipeline blocks it with a security finding.
"""

import subprocess
from pathlib import Path

import pytest

from prism import cli
from prism.config import load_config
from prism.findings import Decision

EXAMPLE = Path(__file__).resolve().parents[2] / "prism.example.yaml"


@pytest.mark.live
def test_prism_local_blocks_a_hardcoded_secret(git_repo: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(git_repo), *args], check=True, capture_output=True, text=True
        )

    git("checkout", "-q", "-b", "feature")
    (git_repo / "app.py").write_text(
        'API_KEY = "sk-live-aa11bb22cc33dd44ee55ff66"  # hardcoded secret\n'
    )
    git("add", "-A")
    git("commit", "-q", "-m", "add key")

    result = cli.run_local_review(load_config(EXAMPLE), target="main", repo=git_repo)

    assert result.decision is Decision.SIGNIFICANT_CONCERNS
    assert any(f.category == "security" for f in result.findings)
