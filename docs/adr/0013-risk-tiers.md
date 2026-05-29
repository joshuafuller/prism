# 0013. Risk tiers — scale reviewers and effort by diff

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Running every reviewer at high effort on a one-line typo wastes the subscription's
rate-limit budget (our equivalent of Cloudflare's token cost). The article classifies each
change into a risk tier and runs a different reviewer set per tier, and always escalates
security-sensitive paths. We want the same, expressed through our config-driven reviewer
model rather than hardcoded tier→agent tables.

## Decision

Add `RiskTier` = `trivial < lite < full` and `assess_risk_tier(files)`:

- **full** if `>50` files **or** any security-sensitive path is touched;
- **trivial** if `≤10` changed lines and `≤20` files;
- **lite** if `≤100` changed lines and `≤20` files;
- **full** otherwise.

Security-sensitive = `auth/ oauth/ jwt/ crypto/ rbac/ permissions/ middleware/`,
`.github/workflows/ .gitlab-ci.yml Dockerfile helm/ k8s/ terraform/ tofu/ deployment/`.

Each reviewer carries an optional `min_tier` (default `trivial` = always runs). A reviewer
runs when `assessed_tier ≥ reviewer.min_tier`. The coordinator's effort is lowered to
`low` on a `trivial` change (the article downgrades the coordinator model). Skipped-by-tier
reviewers are **reported** (no silent truncation, ADR-0012), distinct from runtime skips.

## Consequences

- A typo fix runs a minimal set at low effort; a security or large change runs everything.
- Tiering is deterministic and unit-testable (no LLM needed to test selection).
- Security-sensitive paths can never be under-reviewed.
- Config gains one optional field (`min_tier`); defaults preserve current behavior.
