# 0005. Beads (`bd`) as the work-tracking system of record

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Prism is built spec-driven + TDD across multiple sessions, with AI assistance that loses
context on compaction. Work items, dependencies, and status need to persist outside the
conversation and outside ephemeral in-session task lists.

## Decision

We will use **beads (`bd`)** as the system of record for all work. `bd init` is run in
the repo (issue prefix `prism-`, embedded Dolt backend, git-backed). The implementation
plan is materialized as `bd` issues with explicit dependencies. In-session TodoWrite is
scratch only and is never authoritative. Critical decisions are additionally recorded as
ADRs (this directory).

## Consequences

- Work survives session boundaries and context compaction; dependencies are explicit and
  queryable (`bd ready`, `bd blocked`).
- Git-backed: issue state is versioned alongside code.
- Trade-off: a second tool to keep in sync; mitigated because `bd` auto-commits its store.
- Reversible: issues can be exported (`bd export` → JSONL) and migrated.
