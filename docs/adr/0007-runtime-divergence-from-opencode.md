# 0007. Runtime: subscription CLIs replace OpenCode

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

The reference system (Cloudflare) runs reviewers on **OpenCode**, a server-first coding
agent: they create sessions over an SDK, stream JSONL, and use `session.idle` events to
know when a reviewer is done. Their `spawn_reviewers` in-process tool scheduler exists
largely to manage concurrent SDK sessions and answer the hard question *"when is an LLM
session actually done?"* (3s polling, 60s inactivity kills).

Prism's defining constraint (ADR-0001/0002) is to run on the user's **subscriptions** via
the `claude` and `codex` CLIs, not an API/SDK. So we cannot adopt OpenCode's session model
wholesale, and we shouldn't reinvent it either.

## Decision

We will treat each reviewer/coordinator invocation as a **one-shot subprocess** to a
subscription CLI, behind the `Engine` interface (ADR-0001). Specifically:

- Prompts are written to the CLI's **stdin**, never argv (avoids `E2BIG`/`ARG_MAX` on
  large diffs — a lesson learned the hard way by Cloudflare).
- Done-detection comes from **process exit**, not session events. A per-reviewer timeout
  handles hangs; no polling scheduler is needed.
- Concurrency is plain `asyncio` over subprocesses, not an SDK session manager.
- The Engine parses the CLI's JSONL/JSON output to capture the result and token usage,
  retries once on a `length` (truncation) finish reason, and emits a periodic
  "thinking…" heartbeat in interactive (local) mode.

We keep the *concepts* (specialized reviewers, shared context, judge pass, structured
findings) and drop the *OpenCode-specific machinery*.

## Consequences

- **Net simplification:** the reference system's hardest runtime problem (session done-ness)
  largely disappears — one-shot processes exit when finished.
- The CLIs are themselves agentic (read files, grep), so reviewers can still explore the
  repo without us building a tool layer.
- We give up OpenCode's polished streaming/session SDK and its upstream ecosystem; we own
  subprocess + JSONL parsing instead (isolated in the Engine base, tested with a fake).
- If we ever need server-style concurrency or a richer agent loop, an OpenCode-backed
  `Engine`/`Coordinator` impl can be added behind the existing seams (ADR-0008) without a
  rewrite.
