# 0001. Subscription-CLI-first runtime, API-key fallback

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Prism runs many LLM reviewer sessions per diff. The dominant cost driver is model
inference. The owner has Claude Max and ChatGPT subscriptions and wants to avoid
per-token API billing "if possible," while still allowing API keys at work or for users
without subscriptions. The reference design (Cloudflare) assumed direct API calls and
hardcoded model IDs — which both bills per token and goes stale on every model release.

Options considered:
1. **API-only** — simplest, matches the reference doc literally, but bills every run and
   violates the cost goal.
2. **CLI-only** — drive `claude`/`codex` CLIs (subscription, $0); no fallback, so a
   throttled subscription or a keyless environment has no escape hatch.
3. **CLI-first with API fallback** — abstract over both execution modes.

## Decision

We will make the **Engine** a single abstraction with two execution modes behind one
interface: subscription CLIs (`claude-cli`, `codex-cli`) as the default, and direct API
SDK calls (`anthropic-api`, `openai-api`) as an opt-in, per-reviewer fallback selected by
config. All LLM access flows through `Engine.run()`. Model versions are never hardcoded:
CLIs use the subscription's current default; API engines take a model id from config.

## Consequences

- $0 marginal token cost by default; API billing is explicit and opt-in.
- Model freshness (e.g. Opus 4.8) is automatic on the CLI path — no code change.
- The Engine interface is the one place tests fake, so no test ever calls a real model.
- Cost: two execution paths to implement and test; CLI subprocess parsing is less
  structured than an SDK and needs a repair-retry layer for JSON output.
- Reversible: dropping a mode is deleting an Engine impl; the interface stays.
