# Cloudflare AI Code Review — Lessons, mapped to Prism

Source: *"Orchestrating AI Code Review at scale"*, Cloudflare blog, 2026-04-20 (Ryan
Skidmore). This is the reference system Prism rebuilds. We stand on what they learned
rather than re-deriving it. This doc records the lessons and how each maps to a Prism
decision — so the plan rests on them.

## 1. The failure mode we must avoid (their origin story)

They first tried "grab a git diff, shove it into a half-baked prompt, ask an LLM to find
bugs." Result: a firehose of vague suggestions, hallucinated syntax errors, and
"consider adding error handling" on functions that already had it. **Naive
diff→prompt→bugs does not work on real codebases.** Everything below exists to beat this.

→ Prism: specialized reviewers + judge pass + structured findings, never one generic
prompt. (spec §5, §8–9)

## 2. "What NOT to Flag" is where the value is

Their stated key insight: *"telling an LLM what not to do is where the actual prompt
engineering value resides."* Without explicit exclusions you get speculative warnings
devs learn to ignore. Their result: ~1.2 findings/review, biased hard for signal.

→ Prism: **every reviewer markdown prompt leads with What-to-Flag / What-NOT-to-Flag.**
Their security exclusion list (no theoretical risks, no defense-in-depth when primary
defense is fine, nothing in unchanged code, no "consider library X") is reused. This is
the single highest-leverage prompt decision. (ADR-0009, reviewer prompts)

## 3. Pass the prompt via stdin, never argv

They hit `E2BIG` / `ARG_MAX` passing large MR descriptions as CLI args, on a small % of
big MRs. Fix: pass the prompt via **stdin**.

→ Prism: the `Engine` writes prompts to the CLI's **stdin** (`claude -p`, `codex exec`)
from day one. Cheap now, painful to retrofit. (ADR-0007, Engine base)

## 4. Token frugality — for us it's rate-limit survival

They don't embed full diffs; they write per-file patches to a `diff_directory` and a
single `shared-mr-context.txt`, and sub-reviewers read only what's relevant. Duplicating
context across 7 reviewers would 7× token cost. Drove an 85.7% cache hit rate (identical
base prompts + shared context).

→ Prism: same workspace design (`.prism/` with `shared-context.txt` + per-file
`patches/`). On a **subscription** tokens aren't dollars — they're our Max-20x rate-limit
budget. So every frugality lever (shared context, risk tiers, effort knob, don't-flag
lists, identical base prompts) maps to "don't exhaust the rate limit mid-review."
(spec §6, §10)

## 5. One-shot CLIs make their hardest problem disappear

Their single trickiest runtime problem: *"determining when an LLM session is actually
done."* OpenCode is server-first, so they used `session.idle` events + a 3s polling loop
+ 60s-inactivity kills. The whole `spawn_reviewers` SDK scheduler exists for this.

→ Prism diverges here: `claude -p` / `codex exec` are **one-shot** — the subprocess
*exits* when done. We get done-detection from process exit; we only need a timeout for
hangs. We replace the SDK scheduler with plain concurrent subprocesses (asyncio). The
CLIs are still agentic (they read files / grep), so we keep "reviewers explore the code"
for free. This is a genuine *simplification* the CLI runtime buys us. (ADR-0007)

## 6. Streaming / robustness details worth copying

- **JSONL** (not JSON) for logs/events: every line is independently valid, survives an
  early/OOM exit. claude CLI emits JSONL with `--output-format stream-json`.
- **Truncation retry:** a finish reason of `length` means the model was cut off at
  max_tokens → retry. Prism's Engine should detect and retry once.
- **"Model is thinking… (Ns)" heartbeat every 30s** nearly eliminated users cancelling
  jobs they thought were hung. Local mode is interactive → a progress line is worth it.
- Buffer/flush logs (they flush every 100 lines / 50ms) to avoid `appendFileSync` death.

→ Prism MVP-light: stdin prompts + JSONL parse + token capture + one truncation retry +
a simple heartbeat. (Engine base; spec §10)

## 7. Model routing → our effort knob + sub-spread

They tier models: top-tier (Opus/GPT-5.4) for the coordinator only; standard-tier
(Sonnet / GPT-5.3 Codex) for the heavy sub-reviewers; Kimi for light text tasks. All
overridable at runtime via a Workers-KV control plane.

→ Prism: we have two subscriptions, not a model zoo. We tier by **engine + reasoning
effort** (ADR-0006): coordinator = claude high; security = codex high (spread to halve
rate pressure); code_quality = claude medium; light reviewers = low effort. "Trivial tier
downgrades the coordinator" → we lower coordinator *effort* on trivial diffs. Control
plane (KV) is deferred; local config file for now. (spec §7)

## 8. Coordinator judge pass + approval rubric + break glass

Judge pass: dedup (same issue from two reviewers kept once), re-categorize (perf finding
from code-quality → perf), reasonableness filter (drop speculative/nitpick/false-positive/
convention-contradicted; read source to verify if unsure). Strict rubric → VCS action.
**Bias toward approval** — a single warning still approves-with-comments. **Break glass**:
a human comment forces approval, detected *before* review starts, tracked in telemetry.

→ Prism: judge pass + rubric are MVP (spec §5.4). Break glass needs PR-comment triggers →
deferred with the CI/PR-trigger work, but the rubric leaves room for it.

## 9. Risk tiers, diff filtering

`assessRiskTier`: `full` if >50 files or any security-sensitive file; `trivial` if ≤10
lines & ≤20 files; `lite` if ≤100 lines & ≤20 files; else `full`. Security-sensitive
paths always force full. Diff filter strips lock files / `.min.*` / `.map`, scans first
lines for `@generated` / `eslint-disable` markers — **but exempts DB migrations** even if
marked generated.

→ Prism: diff filter + migration exemption are MVP (spec §6). Full risk-tier auto-classify
is roadmap phase 2, but the reviewer-selection seam is built so it slots in.

## 10. Resilience (deferred, but design for it)

Circuit breaker (Hystrix-style: closed/open/half-open per model tier), failback chains
within a model family, one probe after a 2-min cooldown. Error classifier: only retryable
API errors (429/503) trigger failback; auth errors, context overflow, aborts, schema
errors do **not** (a different model won't fix them). Separate coordinator-level failback.

→ Prism: full circuit breakers are roadmap phase 3. The MVP equivalent is the
**API-fallback engine** (ADR-0001) as the "failback" target when a subscription throttles,
plus the same error-classification rule (don't retry auth/context/abort). (spec §3, §12)

## 11. Honest limitations (set expectations)

AI review is **not** a human replacement. Weak at: architectural intent ("why was this
designed this way"), cross-system impact (flags a contract change, can't verify all
consumers updated), subtle concurrency/race bugs from a static diff. Cost scales with
diff size; warn when the coordinator prompt exceeds ~50% of the context window.

→ Prism: README states these limits plainly. The judge pass should down-rank findings
that assert cross-system or architectural claims it can't verify from the diff.

## 12. Validation (why this architecture is worth copying)

30 days: 131,246 runs / 48,095 MRs / 5,169 repos. Median review 3m39s. Break glass 0.6%.
~1.2 findings/review (deliberately low — signal over noise). Code-quality reviewer ≈ half
all findings; security flags the highest % critical. Risk tiers cut cost ~8× (trivial
$0.20 vs full $1.68). The numbers validate: specialized + judge + tiers + don't-flag
prompts → fast, cheap, trusted reviews.
