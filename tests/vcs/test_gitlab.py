from prism.vcs.gitlab import GitLabProvider


class FakeGlab:
    """Records (argv, stdin) calls; returns scripted stdout per call."""

    def __init__(self, outputs: list[str] | None = None) -> None:
        self._outputs = outputs or [""]
        self.calls: list[tuple[list[str], str]] = []

    def __call__(self, argv: list[str], stdin: str = "") -> str:
        self.calls.append((argv, stdin))
        return self._outputs[min(len(self.calls) - 1, len(self._outputs) - 1)]


def test_auth_account_returns_username() -> None:
    glab = FakeGlab(['{"username": "joshuafuller", "name": "Josh"}'])
    assert GitLabProvider(run=glab).auth_account() == "joshuafuller"
    assert glab.calls[0][0][:3] == ["glab", "api", "user"]


def test_post_summary_uses_mr_note_create_with_body_on_stdin() -> None:
    glab = FakeGlab()
    GitLabProvider(run=glab).post_summary(482, "## Prism review\n\nLooks good.")
    argv, stdin = glab.calls[0]
    assert argv[:4] == ["glab", "mr", "note", "create"]
    assert "482" in argv
    assert stdin == "## Prism review\n\nLooks good."  # body via stdin, not argv
