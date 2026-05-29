# 0006. Reasoning effort as a first-class routing knob

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Published SWE-Bench Pro data for Claude Opus 4.8 shows pass rate rising with reasoning
effort while mean output tokens scale ~10× from low→max (log scale); notably, Opus 4.8 at
*low* effort matches Opus 4.7 at *max*. On a **subscription**, output tokens are not a
dollar cost — they are rate-limit budget. So spending maximum effort on every reviewer
would burn the rate limit (and slow reviews) for little gain on easy reviewers.

## Decision

We will treat **reasoning effort** (`low | medium | high | xhigh | max`) as a first-class,
per-reviewer routing parameter in config, alongside engine selection — not a global
constant. Judgment-heavy roles (coordinator, security) run high effort; cheap roles
(documentation, release) run low. To further spread rate-limit pressure, default routing
distributes reviewers across both subscriptions (e.g. `security` → `codex-cli`, others →
`claude-cli`), with the ADR-0001 API path available for burst overflow.

## Consequences

- Quality/throughput tuned per reviewer instead of one blunt setting; better use of a
  fixed subscription rate budget.
- The Engine interface carries `effort`; each engine maps it to its CLI/SDK equivalent
  (e.g. Codex effort flag, Claude thinking budget).
- Adds a config dimension to document and test; defaults must be sensible.
- Informs the future model-router and failback work (roadmap phase 3).
