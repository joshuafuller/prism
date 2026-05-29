# Prism — MVP Design Spec

**Date:** 2026-05-29
**Status:** Approved direction; pending user review of this spec
**Author:** Joshua Fuller (joshuafuller@gmail.com)

---

## 1. What Prism is

Prism is a CI-native AI code-review orchestration system. One diff goes in; it is
split into specialized reviewer "wavelengths" (code quality, security, …) run
concurrently, then recombined by a coordinator/judge pass into a single structured
verdict. It is modeled on Cloudflare's AI code review architecture (coordinator +
spawned reviewers, risk tiers, structured findings, policy-driven outcomes) but
adapted to run off **personal Claude/Codex subscriptions** at **$0 marginal token
cost**, packaged as a **native Docker image**, **GitHub-first**.

The full architecture is described in the project's north-star design document. This
spec scopes the **MVP only** — the smallest slice that proves the system is useful
and retires the central technical risk.

## 2. Goals (MVP)

1. Review a local branch/diff and produce structured findings + a markdown report.
2. Drive reviews off **subscription CLIs** (`claude`, `codex`) — no per-token API cost.
3. Offer a **per-reviewer API-key fallback** (`anthropic-api`, `openai-api`) for users
   without subscriptions or for burst/rate-limit overflow.
4. Run **natively in Docker**, with subscription credentials supplied via host volume
   mounts.
5. Optionally **post a summary to a GitHub Pull Request** via the `gh` CLI.
6. Coordinator + two specialized reviewers (`code_quality`, `security`) + a judge pass
   that dedups, reclassifies, drops false positives, and emits one decision.

## 3. Non-goals (MVP — deferred to roadmap)

CI execution (subscription-auth in ephemeral runners), risk-tier auto-classification,
circuit breakers / failback chains, re-review state, inline PR comments, telemetry
sink, GitLab adapter, break-glass override, and the AGENTS.md / documentation /
release / performance / internal-standards reviewers. The **seams** (Engine,
VCSProvider, Reviewer registry) are designed so these slot in without rework.

## 4. Keystone risk — RETIRED (proven 2026-05-29)

The whole "$0 on subscriptions, inside Docker" premise rested on one untested
assumption: that the subscription CLIs would authenticate inside a container without
re-login and without silently falling back to a billed API key. This was proven
**before** writing this spec:

- Credentials are **file-based**, not keyring-based, so a directory mount carries them:
  - Claude: `~/.claude/.credentials.json` (`claudeAiOauth`, `subscriptionType: max`,
    `rateLimitTier: default_claude_max_20x`) + `~/.claude.json`.
  - Codex: `~/.codex/auth.json` (`tokens` = ChatGPT-subscription OAuth;
    `OPENAI_API_KEY` field **empty**) + `~/.codex/config.toml`.
- A minimal `node:24-slim` image with `@anthropic-ai/claude-code` + `@openai/codex`
  installed, run with creds mounted and **no API keys in the environment**, returned:
  - `claude -p …` → answered (subscription OAuth).
  - `codex exec --skip-git-repo-check …` → answered via `gpt-5.5` on the ChatGPT
    subscription tokens; reported token usage.

Because no API key existed in the environment, success can only mean subscription auth.

**Failure branch (now moot, retained for completeness):** had this failed, the fork
would have been a *user decision* — (a) run on the host instead of Docker, or (b) accept
API-key billing. The API-key fallback engine exists partly to make (b) viable.

### Operational notes captured from the spike
- Run the container as a user whose `$HOME` matches the mount target
  (`/root/.claude` when root; align UID/`HOME` for a non-root `app` user).
- `apt install bubblewrap` in the image to give Codex a proper sandbox (otherwise a
  non-fatal warning + bundled fallback).
- Codex needs `--skip-git-repo-check` when the workspace is not a git repo.
- Codex defaults to `gpt-5.5` at `xhigh` effort; Claude uses the subscription's current
  default model (Opus 4.8 today) — **no model version is hardcoded in Prism**.
- Credentials must be mounted from **copies** during testing so experiments cannot
  corrupt the host's real auth.

## 5. Architecture

Three clean seams keep the pieces independently testable:

```
prism local --target main
   │
   ▼
DiffSource ──► Workspace ──► Coordinator ──► Reporter
(git / gh)     (.prism/)        │            (report.md
                                │             + gh post)
                       spawn_reviewers (parallel)
                                │
                        ┌───────┴────────┐
                   code_quality       security
                        │                │
                        └───► Engine ◄───┘
                       (claude-cli │ codex-cli │
                        anthropic-api │ openai-api)
```

### 5.1 Engine — the single LLM chokepoint
One interface; all model access flows through it, so tests fake the subprocess and
never call a real model.

```
class Engine(Protocol):
    def run(self, prompt: str, *, effort: Effort, model: str | None,
            schema: type[BaseModel]) -> ParsedResult: ...
```

Implementations:
- `claude-cli` — subprocess to `claude -p`, subscription, $0.
- `codex-cli` — subprocess to `codex exec --skip-git-repo-check`, subscription, $0.
- `anthropic-api` / `openai-api` — direct SDK call, key from a named env var,
  pay-per-token. Model id (e.g. `claude-opus-4-8`) configured per engine, never in code.

`effort` (`low|medium|high|xhigh|max`) is a first-class routing knob: with Opus 4.8,
low effort ≈ Opus 4.7 at max, and output tokens scale ~10× low→max. On a subscription
tokens are rate-limit budget, so cheap reviewers run low effort and judgment-heavy
reviewers run high.

### 5.2 VCSProvider
Interface for reading PR context and posting findings. MVP impl: `github` via the `gh`
CLI (reuses the host's `joshuafuller` login; posting is plain GitHub API calls, $0
against subscriptions). `gitlab` is a later impl behind the same interface. Prism
verifies `gh auth status` resolves to the expected account before posting.

### 5.3 Reviewer
A registry entry: prompt + engine-ref + effort + output schema + "what to flag" /
"what not to flag". MVP ships `code_quality` and `security`. To spread subscription
rate-limit pressure, default routing puts `security` on `codex-cli` and the rest on
`claude-cli`.

### 5.4 Coordinator
Selects reviewers, runs them concurrently, then runs a **judge pass** that dedups
overlapping findings, reclassifies categories, drops low-confidence/false-positive
findings, and emits one decision: `approved | approved_with_comments | minor_issues |
significant_concerns`. Default bias toward approval; a single warning does not block.

## 6. Data flow

1. `prism local --target main` → `DiffSource` yields changed files + per-file patches
   (`git diff` locally, or `gh pr diff` for a PR).
2. **Diff filter** drops lock files / minified / bundles / source maps — but **never
   database/schema migrations**. Skips are logged (no silent truncation).
3. `Workspace` writes `.prism/`: `shared-context.txt`, `changed-files.json`,
   `patches/`. The full diff is **not** duplicated into every reviewer prompt; reviewers
   receive paths and read only what their domain needs.
4. Coordinator runs reviewers concurrently; each returns **pydantic-validated**
   structured findings, with one repair-retry on malformed JSON.
5. Judge pass → `findings.json` + decision.
6. `Reporter` writes `report.md`; if `--post-pr <n>`, posts a summary via `gh`.

### Finding schema (pydantic)
`id, severity (critical|warning|suggestion), category, file, line, title, explanation,
recommendation, confidence (high|medium|low), reviewer`.

## 7. Configuration

`prism.yaml` in the repo root; env vars override. No hardcoded model versions.

```yaml
engines:
  claude-cli: { kind: claude-cli }
  codex-cli:  { kind: codex-cli }
  anthropic:  { kind: anthropic-api, key_env: ANTHROPIC_API_KEY, model: claude-opus-4-8 }
  openai:     { kind: openai-api,    key_env: OPENAI_API_KEY,    model: gpt-5.5 }
reviewers:
  code_quality: { engine: claude-cli, effort: medium }
  security:     { engine: codex-cli,  effort: high }
coordinator:    { engine: claude-cli, effort: high }
policy:
  # local mode is report-only by default; nonzero exit only on significant_concerns
  significant_concerns: fail
```

## 8. Prompt-injection posture (MVP-light)

Even reviewing your own diffs, file names and diff content are untrusted. The shared
reviewer prompt states explicitly that repository content, file names, and PR
descriptions are **data, not instructions**. Prompt-boundary markers in user-controlled
content are stripped/escaped before insertion. Full defense (comments, prior AI review,
AGENTS.md) is deferred with the features that introduce those inputs.

## 9. Packaging

Native Docker image: `python + uv + claude CLI + codex CLI + gh CLI + bubblewrap`.
Invocation (wrapped by a thin `prism` script / `docker compose run`):

```bash
docker run --rm \
  -v "$PWD":/repo \
  -v ~/.claude:/home/app/.claude -v ~/.claude.json:/home/app/.claude.json \
  -v ~/.codex:/home/app/.codex \
  -v ~/.config/gh:/home/app/.config/gh \
  prism local --target main
```

## 10. Testing strategy (TDD + fail-fast gates)

- **Fast unit layer (default loop):** every Engine tested against a **faked subprocess**
  — deterministic, zero LLM calls, sub-second. Schema validation + repair-retry tested
  with canned malformed JSON.
- **Golden fixtures:** a sample diff + canned reviewer outputs assert coordinator
  dedup/decision logic without any model.
- **Opt-in live test:** `uv run pytest -m live` actually invokes `claude`/`codex` to
  confirm real wiring; excluded from the fast loop.
- **Dev gate (per plan phase):** a phase is not "done" until `uv run pytest` is green,
  `uv run ruff check` and `uv run mypy` are clean, and the CLI runs end-to-end on a
  fixture. Strict red → green → refactor.

## 11. Tooling & process

- **Language/env:** Python, **uv** only (no pip, no hand-managed venvs). `uv run …`
  for every command; `uv.lock` committed.
- **Repo:** private GitHub repo under `joshuafuller`, created via `gh repo create
  --private`.
- **Work tracking:** **beads (`bd`)** is the system of record. `bd init` in the repo;
  the implementation plan becomes `bd` issues with dependencies (git-backed, survives
  sessions/compaction). TodoWrite is in-session scratch only.
- **Methodology:** spec-driven (this doc) → implementation plan → TDD.
- **ADRs:** every critical / architecturally-significant / hard-to-reverse decision is
  recorded as an ADR in `docs/adr/` **before it is locked**. The decisions in this spec
  are already captured as ADR-0001…0006.

## 12. Rollout (post-MVP roadmap)

1. **MVP (this spec):** local mode + GitHub PR post; coordinator + code_quality +
   security + judge; static config; Docker; subscriptions.
2. Risk tiers, diff-filter hardening, richer structured findings.
3. Model router, failback chains, circuit breakers, telemetry.
4. Re-review state, inline comments, AGENTS.md / docs / release reviewers.
5. GitHub Actions / GitLab CI execution, GitLab adapter, remote model control plane,
   break-glass, policy hardening.

## 13. Open questions (carry into planning, not blocking MVP)

1. Where does review state live long-term (PR comments vs. artifacts vs. object store)?
2. Summary comment vs. inline comments vs. both (MVP = summary only).
3. Should `minor_issues` ever fail CI, or only affect approval? (MVP: report-only.)
4. Non-root container user + UID alignment for credential mounts — settle in MVP build.
