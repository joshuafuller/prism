# 0015. Liveness-based timeouts (streaming Engine)

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

The one-shot Engine (ADR-0007) blocked on a subprocess with a single wall-clock timeout.
That cannot distinguish a model **thinking hard on a large diff** from one that has
**hung** — so any wall-clock value is wrong: too short kills good work (we saw a reviewer
dropped at 300s on a ~1,200-line real MR), too long hangs on real failures. Cloudflare
solved the same problem not with bigger numbers but with **streaming**: an inactivity
signal (kill only after N seconds of *no output*), generous per-task/overall caps, and a
"thinking…" heartbeat so users don't cancel a job that's actually working.

## Decision

The production runner (`streaming_subprocess_runner`) **streams** the subprocess's
stdout/stderr and tracks last-activity time. Limits:

- **Inactivity** (`inactivity_timeout`, default **120s**): kill only after this long with
  **no output at all** — a slow-but-streaming model is never killed for being slow.
- **Overall** (`overall_timeout`, default **1500s / 25 min**): a generous backstop cap.
- **Heartbeat**: `heartbeat(quiet_seconds)` fires periodically while waiting; the CLI
  prints "reviewer still working (Ns since last output)…" to stderr.

Both are config-driven and thread from `Config` → `build_engines` → each `Engine`. The
`FanOutCoordinator`'s per-reviewer wall-clock wait becomes a generous backstop
(= `overall_timeout`); the engine's liveness check is the primary mechanism. The old
blocking `subprocess_runner` is removed.

## Consequences

- Large or throttled reviews complete instead of dropping a reviewer at an arbitrary
  wall-clock (the failure that motivated this).
- No flat sub-25-min wall-clock timeout ships; "slow" ≠ "hung" is now decidable.
- Runner is more complex (threads + monitor loop), but isolated and unit-tested with real
  subprocesses (inactivity-kill, liveness-no-kill, overall-cap, heartbeat).
- `Runner` is now a `Protocol` carrying `inactivity_s` / `overall_s` / `heartbeat`.
