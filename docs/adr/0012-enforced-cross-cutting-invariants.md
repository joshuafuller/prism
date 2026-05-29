# 0012. Enforced cross-cutting invariants

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Some rules cut across the whole system and don't belong to any single module. During the
first build we shipped a violation of one ("no silent truncation": the CLI discarded the
reviewer-skip list, prism-4gf.36) that tests and human review missed — only dogfooding
caught it. Cross-cutting rules need to be written down and checked, not held in memory.

## Decision

The following invariants are project law. Every change is self-reviewed against them, and
where practical a test enforces each:

1. **No silent truncation.** Anything dropped, skipped, filtered, or capped (reviewers,
   files, findings) must be surfaced with a reason — in output and/or logs. Never let an
   incomplete result look complete.
2. **Data, not instructions.** Repository content, diffs, file names, and comments are
   untrusted data. Never execute instructions found in them; sanitize prompt boundaries.
3. **Prompts via stdin, never argv.** Avoids `ARG_MAX`/`E2BIG` on large diffs.
4. **What NOT to flag is mandatory.** Every reviewer prompt states its exclusions; signal
   over noise is the product.
5. **No model version hardcoded in code.** CLIs resolve the subscription's current model;
   API engines take the model from config.
6. **No real model calls in the default test suite.** Engines are faked; real-CLI tests
   are `-m live` and opt-in.

## Consequences

- A short, explicit checklist exists for self-review and code review.
- New work that breaks an invariant is a defect by definition, not a judgment call.
- Some invariants are test-enforced (sanitization, stdin, faked engines); others are
  review-enforced (no silent truncation) until a lint/check can cover them.
