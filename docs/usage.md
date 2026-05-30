# Usage Guide

How to configure Prism, run a review, and read the result. For wiring Prism into an AI
coding agent, see [Using Prism with AI Agents](ai-agents.md).

## Contents

- [Install](#install)
- [Configure (`prism.yaml`)](#configure-prismyaml)
- [Run a review](#run-a-review)
- [Read the output](#read-the-output)
- [Risk tiers: what runs when](#risk-tiers-what-runs-when)
- [Post to a PR or MR](#post-to-a-pr-or-mr)
- [Use in CI](#use-in-ci)
- [The `.prism/` directory](#the-prism-directory)
- [Troubleshooting](#troubleshooting)

## Install

Prism needs your subscription CLIs logged in on the host first:

```bash
claude            # log in to your Claude subscription (Max, etc.)
codex             # log in to your ChatGPT/Codex subscription
gh auth login     # (optional) to post to GitHub PRs; glab for GitLab
```

Then pick a runtime.

**Docker (recommended)** — the image bundles the `claude`, `codex`, and `gh` CLIs, so the
only host requirements are Docker and your logins. It's a multistage
[Chainguard wolfi](https://www.chainguard.dev/) build (~1.1 GB, **0 known CVEs** at
release) containing Python 3.12, Node, the two review CLIs, `gh`, `git`, and `bubblewrap`
(codex's sandbox). `uv` and build tooling are dropped from the final image.

```bash
docker build -t prism .                  # build once
# Non-default host UID? add:  --build-arg APP_UID="$(id -u)"
bin/prism local --target main            # run a review
```

`bin/prism` is the **recommended runner**. It mounts your repo at `/repo` and a
**throwaway copy** of your `~/.claude`, `~/.codex`, and `~/.config/gh` credentials — the
CLIs authenticate with your existing logins while your real host credentials stay
untouched (a prompt-injected reviewer can't tamper with them), and the copy is deleted on
exit. Subscriptions work inside the container with **no API key in the environment** (see
[ADR-0002](adr/)).

**Docker Compose** — a familiar build/run wrapper:

```bash
docker compose build                                  # build the image
docker compose run --rm prism local --target main     # review (args go after the service)
# If your host UID isn't 1000:  APP_UID=$(id -u) docker compose build
```

Compose bind-mounts your real credential directories. For the hardened throwaway-copy
isolation, prefer `bin/prism` (above). See `docker-compose.yml` for the security note.

**Local (host Python)** — if you have the CLIs plus [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run prism local --target main --config prism.yaml
```

## Configure (`prism.yaml`)

Copy the example and edit:

```bash
cp prism.example.yaml prism.yaml
```

`prism.yaml` is your local config — Prism's own repo gitignores it, so copying it here
never dirties the tree. In *your* project, commit it if you want your team to share one
config.

A config has four parts:

```yaml
engines:                      # the LLM backends Prism may use
  claude-cli:
    kind: claude-cli          # drives the `claude` CLI (your Claude subscription)
  codex-cli:
    kind: codex-cli           # drives the `codex` CLI (your ChatGPT/Codex subscription)

reviewers:                    # each runs concurrently with a scoped prompt
  code_quality:
    engine: claude-cli
    effort: medium
  security:
    engine: codex-cli         # spread across both subscriptions to ease rate limits
    effort: high
  performance:
    engine: claude-cli
    effort: medium

coordinator:                  # the judge: dedupes, filters, decides
  engine: claude-cli
  effort: high

policy:
  fail_on: significant_concerns   # nonzero exit only at this decision or worse

inactivity_timeout: 120       # kill a reviewer after N seconds with NO output (hung)
overall_timeout: 1500         # generous backstop cap per reviewer
```

### Reference

| Key | Values | Notes |
|-----|--------|-------|
| `engines.<n>.kind` | `claude-cli`, `codex-cli`, `anthropic-api`, `openai-api` | API kinds are an opt-in fallback (deferred); CLI kinds use your subscription. |
| `engines.<n>.model` | any model id | Optional. Omit to use the subscription's current default — nothing is hardcoded. |
| `reviewers.<n>.engine` | an engine name | Which backend this reviewer runs on. |
| `reviewers.<n>.effort` | `low`, `medium`, `high`, `xhigh`, `max` | Reasoning effort ([ADR-0006](adr/)). On a subscription, effort is your rate-limit budget. |
| `reviewers.<n>.min_tier` | `trivial`, `lite`, `full` | Only run this reviewer when the diff reaches this risk tier. See [Risk tiers](#risk-tiers-what-runs-when). |
| `coordinator.engine` / `effort` | as above | The judge. Give it your strongest setup. |
| `policy.fail_on` | `approved`, `approved_with_comments`, `minor_issues`, `significant_concerns` | The verdict at which `prism local` exits nonzero. |
| `inactivity_timeout` | seconds | Liveness limit: a reviewer is killed only after this long with **no** output, never for being slow ([ADR-0015](adr/)). |
| `overall_timeout` | seconds | Hard backstop per reviewer. |

The shipped reviewers are `code_quality`, `security`, and `performance`. `documentation`
and `release` reviewers also exist — uncomment them in `prism.example.yaml` to enable. To
write your own, see [Add your own reviewer](../README.md#add-your-own-reviewer).

### Choosing engines: Claude vs Codex

Prism picks an engine **per reviewer** (and for the coordinator) via the `engine:` field —
that's how you decide who runs what. Every `engine` must be defined in the `engines:` block
and backed by a CLI you're logged into.

- **You have both subscriptions** (the default example): spread reviewers across
  `claude-cli` and `codex-cli`. Two providers halves the rate-limit pressure on either, and
  gives the security reviewer a second model's perspective.
- **You have only one** (Claude *or* Codex): point every reviewer **and** the coordinator at
  that one engine, and drop the other engine block. Claude-only example:

  ```yaml
  engines:
    claude-cli:
      kind: claude-cli
  reviewers:
    code_quality: { engine: claude-cli, effort: medium }
    security:     { engine: claude-cli, effort: high }
    performance:  { engine: claude-cli, effort: medium }
  coordinator:
    engine: claude-cli
    effort: high
  ```

  (For Codex-only, swap every `claude-cli` for `codex-cli`.)

> The **coordinator** is the judge — give it your strongest engine and effort. If a
> reviewer's engine isn't logged in, that reviewer is **skipped with a recorded reason** and
> the review still completes — so a missing second subscription degrades gracefully instead
> of failing the run.

## Run a review

Prism reviews the diff between a target ref and your working tree.

```bash
# Docker
bin/prism local --target main

# Local
uv run prism local --target main --config prism.yaml
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--target <ref>` | (required) | Git ref to diff against, e.g. `main` or `HEAD~1`. |
| `--config <path>` | `prism.yaml` | Path to your config. |
| `--repo <path>` | `.` | Repo working tree to review. |
| `--post-pr <n>` | — | Also post the summary to GitHub PR #n. |
| `--post-mr <n>` | — | Also post the summary to GitLab MR !n. |

A typical loop: make changes on a branch, run `prism local --target main`, read the
report, fix, repeat.

## Read the output

Every run writes two files (plus [more](#the-prism-directory)):

**`.prism/report.md`** — the human-readable review: a verdict, a summary, and findings
grouped by severity. This is what gets posted to a PR/MR.

**`.prism/findings.json`** — the same findings as a structured array, for CI and tools:

```json
[
  {
    "id": "sql-injection-order-search",
    "severity": "critical",
    "category": "security",
    "file": "api/orders.py",
    "line": 42,
    "title": "SQL injection in order search",
    "explanation": "The handler formats the user-supplied `q` straight into the query ...",
    "recommendation": "Use a parameterized query and never interpolate user input into SQL.",
    "confidence": "high",
    "reviewer": "security"
  }
]
```

| Field | Values |
|-------|--------|
| `severity` | `critical` · `warning` · `suggestion` |
| `category` | `security` · `code_quality` · `performance` · `documentation` · `release` · `other` |
| `confidence` | `high` · `medium` · `low` |
| `file` / `line` | location in the diff |
| `title` / `explanation` / `recommendation` | what, why, and the fix |
| `reviewer` | which reviewer raised it |

The overall **decision** (in `report.md` and the exit code) is one of:

| Decision | Meaning |
|----------|---------|
| `approved` | No findings, or only trivial suggestions. |
| `approved_with_comments` | Suggestions, or isolated warnings with no production risk. |
| `minor_issues` | Multiple warnings suggesting a real risk pattern; nothing critical. |
| `significant_concerns` | A critical item, exploitable vulnerability, likely outage, or data loss. |

## Risk tiers: what runs when

Prism classifies each diff into a tier and uses it to decide which reviewers run and how
hard the coordinator thinks — so a one-line typo fix doesn't burn a full security pass.

| Tier | Roughly | Effect |
|------|---------|--------|
| `trivial` | tiny diffs | Minimal reviewers; coordinator runs at low effort. |
| `lite` | small diffs | Default reviewers run. |
| `full` | large, or **security-sensitive**, or **AST-risky** | Everything runs at full strength. |

A diff that touches security-sensitive paths, or that introduces risky constructs
(`eval`, `exec`, `subprocess(..., shell=True)`, `pickle`, …) detected by AST analysis,
escalates to `full` even if it's small. Use `reviewers.<n>.min_tier` to scope an expensive
reviewer to higher tiers. See [ADR-0013](adr/) / [ADR-0014](adr/).

## Post to a PR or MR

```bash
bin/prism local --target main --post-pr 42    # GitHub PR #42 (needs gh authenticated)
bin/prism local --target main --post-mr 77    # GitLab MR !77 (needs glab authenticated)
```

Prism posts `report.md` as a single summary comment. Posting is identity-checked first
(it fails loudly if the CLI isn't authenticated) and never blocks the local review.

## Use in CI

`prism local` exits nonzero only when the decision is at least as severe as your
`policy.fail_on`, so it works as a gate:

```yaml
# example CI step
- run: prism local --target "$BASE_REF" --config prism.yaml
# job fails if the verdict reaches policy.fail_on (default: significant_concerns)
```

Set `fail_on: minor_issues` to be stricter, or `approved_with_comments` to block on almost
anything.

## The `.prism/` directory

Each run writes to `.prism/` (gitignored):

| Path | What |
|------|------|
| `report.md` | Human-readable review. |
| `findings.json` | Structured findings (above). |
| `runs/<label>.jsonl` | Raw event stream per reviewer + the coordinator — what each model did, including any source it read to verify. For debugging and tuning. |
| `telemetry.jsonl` | One line per run: tier, reviewers run/skipped, findings by severity, decision, duration, tokens. |

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `missing $HOME/.claude — log in on the host first` | Run `claude` (and `codex`) on the host to authenticate before using Docker. |
| `FileNotFoundError: 'prism.yaml'` | No config in the repo. Run `cp prism.example.yaml prism.yaml`, or pass `--config`. |
| A reviewer is "skipped (timed out)" | It produced no output for `inactivity_timeout` seconds. Raise it, or check the matching `.prism/runs/<label>.jsonl`. |
| Rate-limit / overload errors | You're hitting your subscription's limit. Spread reviewers across both engines, lower `effort`, or reduce diff size. |
| Empty or odd findings | Inspect `.prism/runs/<label>.jsonl` to see exactly what the model received and did. |
