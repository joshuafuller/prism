# 0010. Mandatory Red-Green-Refactor with per-stage commits

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

The project values forced good practices and a codebase that survives pivots without
painful refactors. Early build tasks (prism-4gf.7–.12) were written test-first and
verified failing-then-passing, but the discipline was loose in two ways: (1) the RED step
often failed with `ModuleNotFoundError` rather than a meaningful *assertion* failure, so
it didn't prove the test exercises the intended behavior; and (2) the Red→Green→Refactor
cycle was squashed into one commit per task, so it isn't auditable in git history, and the
REFACTOR step was usually skipped. "It looked like we did not [enforce TDD]." — we need it
enforced, not merely intended.

## Decision

Every task that adds or changes production behavior MUST follow Red-Green-Refactor as
**three separate commits**, in order:

1. **RED** — `test: <behavior> (RED)`. Write one focused failing test. Add only the
   minimal stub needed so the test fails on its **assertion** (not on an import/typo).
   Run it; the failure message must be the expected, behavior-level failure.
2. **GREEN** — `feat: <behavior> (GREEN)` (or `fix:`). Write the minimal code to pass.
   Run the test and the full suite; output must be pristine.
3. **REFACTOR** — `refactor: <what>`. Clean up (dedup, names, extraction) with tests
   staying green. If nothing needs it, say so in the task notes and skip the commit.

The Iron Law applies: **no production code without a failing test first**; code written
before its test is deleted and reimplemented from the test.

Audit trail: the RED commit precedes its GREEN commit in `git log`, proving test-first.
The pre-commit hook lints (not tests), so committing a RED (failing-test) state is allowed;
CI is the gate that must be green on the GREEN/REFACTOR commits once billing is restored.

## Consequences

- Red-Green-Refactor becomes provable from `git log`, not just narrated.
- Reds fail for the right reason, so tests are trustworthy.
- More commits per task (~3×); acceptable for a solo exploratory repo and worth the rigor.
- A RED commit transiently leaves `master` with a failing test; tolerable here because the
  GREEN commit follows immediately and local gates + CI guard the durable state.
- Applies from prism-4gf.13 onward; .7–.12 are not retro-fitted (already green).
