# 0008. Orchestration is a pluggable seam; MVP ships the simplest strategy

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

There are (at least) two ways to orchestrate reviewers:

- **A — Orchestrator fans out, coordinator judges:** deterministic code selects reviewers
  (by risk tier), spawns them concurrently, collects findings, then calls the LLM
  coordinator purely to dedup/filter/decide.
- **B — Coordinator-driven spawn (the reference system):** the coordinator LLM is given a
  `spawn_reviewers` tool and decides at runtime which reviewers to launch.

We do not yet have enough evidence to know which is better for Prism, and the project's
principles are explicit: avoid large painful refactors, expect to learn and pivot, keep
the codebase modular.

## Decision

We will make orchestration a **seam**: a `Coordinator` (review-strategy) interface that
owns "given context + reviewers, produce findings + a decision." The MVP ships **strategy
A** (orchestrator fans out, coordinator judges) because it is the least machinery, fits
one-shot CLIs (ADR-0007), keeps reviewer *selection* in deterministic, unit-testable code,
and uses the LLM only for the judgment it is good at.

Strategy B (and a hybrid where the coordinator may request an extra reviewer) are **not
built now**. If evidence later favors them, they are added as alternative implementations
behind the same `Coordinator` interface.

## Consequences

- The A-vs-B decision stops being a blocker and becomes reversible: a pivot is an
  additive implementation, not a rewrite.
- Reviewer selection is deterministic and testable in the MVP (no LLM needed to test
  "which reviewers run for this diff").
- Slight risk of designing the interface too narrowly for B; mitigated by keeping the
  interface at the level of "context + available reviewers → result," which both
  strategies satisfy.
- Cost: one more interface to define and document — acceptable given the modularity goal.
