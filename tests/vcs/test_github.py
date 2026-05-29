from prism.vcs.github import GitHubProvider


class FakeGh:
    """Records (argv, stdin) calls; returns scripted stdout per call."""

    def __init__(self, outputs: list[str] | None = None) -> None:
        self._outputs = outputs or [""]
        self.calls: list[tuple[list[str], str]] = []

    def __call__(self, argv: list[str], stdin: str = "") -> str:
        self.calls.append((argv, stdin))
        return self._outputs[min(len(self.calls) - 1, len(self._outputs) - 1)]


def test_auth_account_returns_login() -> None:
    gh = FakeGh(["joshuafuller\n"])
    account = GitHubProvider(run=gh).auth_account()
    assert account == "joshuafuller"
    argv = gh.calls[0][0]
    assert argv[:3] == ["gh", "api", "user"]


def test_post_summary_uses_pr_comment_with_body_on_stdin() -> None:
    gh = FakeGh()
    GitHubProvider(run=gh).post_summary(42, "## Prism review\n\nLooks good.")
    argv, stdin = gh.calls[0]
    assert argv[:3] == ["gh", "pr", "comment"]
    assert "42" in argv
    assert "--body-file" in argv and "-" in argv  # body via stdin, not argv
    assert stdin == "## Prism review\n\nLooks good."
