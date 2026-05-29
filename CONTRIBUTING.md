# Contributing to Prism

## Development workflow (mandatory)

Prism is built **spec-driven + test-first**. All work is tracked in
[beads](https://github.com/gastownhall/beads) (`bd`), and every behavior change follows
**Red-Green-Refactor as three commits** (see [ADR-0010](docs/adr/0010-mandatory-tdd-red-green-refactor.md)).

### Per task

```bash
bd ready                       # pick the next unblocked task
bd update <id> --status in_progress
```

Then the cycle:

1. **RED** — write one focused failing test. Add only a minimal stub so it fails on the
   **assertion**, not an import error. Watch it fail for the right reason.
   ```bash
   uv run pytest tests/path/test_x.py -q     # must FAIL on the assertion
   git commit -am "test: <behavior> (RED)"
   ```
2. **GREEN** — minimal code to pass. Full suite + gates green.
   ```bash
   uv run pytest -q && uv run ruff check . && uv run mypy src
   git commit -am "feat: <behavior> (GREEN)"
   ```
3. **REFACTOR** — clean up with tests staying green (or note "nothing to refactor").
   ```bash
   uv run pytest -q
   git commit -am "refactor: <what>"
   ```

```bash
bd close <id>
git push
```

### Rules

- **No production code without a failing test first** (Iron Law). Wrote code first? Delete
  it and reimplement from the test.
- The **pre-commit lint hook** (ruff) is enforced via `core.hooksPath=.githooks`. Set it
  up after cloning: `git config core.hooksPath .githooks`.
- Gates that must be green on GREEN/REFACTOR commits: `uv run pytest -q`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`.
- Unit tests **never call a real model** — engines are exercised through the fake runner
  (`tests/conftest.py`). Tests that hit the real CLIs are marked `@pytest.mark.live` and
  excluded from the default run.
- Adding a reviewer = drop `agents/<name>.md` + one registry line (no core change).

### Tooling

Python 3.12, [uv](https://docs.astral.sh/uv/) only — no pip, no manual venvs.

```bash
uv sync --dev
uv run pytest          # fast suite (LLMs faked)
uv run pytest -m live  # opt-in: real subscription CLIs
```
