# Retrospective — First Build Run

**Date:** 2026-05-29
**Scope:** From empty repo to a working, dogfooded MVP in a single session.
**Outcome:** `prism local` reviews a diff end-to-end on Claude/Codex subscriptions ($0),
locally and natively in Docker, posts to GitHub PRs, and **caught real bugs in its own
codebase**. 32/38 beads issues closed; 79 unit tests + live smoke tests; strict TDD;
10 ADRs. Repo: github.com/joshuafuller/prism (private).

---

## What worked

- **Keystone-first de-risking.** We proved the riskiest assumption — subscription CLIs
  authenticate *inside Docker* with no API key — *before* writing the spec. The whole
  "$0" premise rested on it; proving it first meant we never built on a false floor.
- **Spec → ADRs → plan → TDD pipeline.** The superpowers flow gave a clean, auditable
  progression. ADRs forced the critical decisions to be explicit and reversible.
- **Beads as system of record.** The dependency graph + `bd ready` queue kept a very long
  session coherent; work survived across many tasks without a lost thread.
- **Architecture seams + markdown agents.** `Engine`, `VCSProvider`, reviewer registry,
  and `Coordinator` interfaces, plus prompts-as-markdown (ADR-0009), made every addition
  *additive* — no painful refactors, exactly the stated goal.
- **The "what NOT to flag" prompts.** Across three live runs the output had **zero noise**
  — no style nitpicks, no doc gripes, no hallucinated errors. This is the article's
  central lever and it held.
- **Dogfooding.** Prism reviewing its own repo found two real, unfiled bugs (a silent
  reviewer-skip and an exit-code ordering gap) plus a security finding. Strongest possible
  validation, and it closed the loop: the reviewer enforces the very principles we set.
- **Local CI decoupled from cloud quota.** A pre-push full gate (ruff/format/mypy/pytest)
  means quality is enforced on every push regardless of GitHub Actions availability.

## What didn't (friction & misses)

- **TDD rigor was loose for the first ~6 tasks.** REDs were often `ModuleNotFoundError`
  (import missing) rather than assertion-level failures, REFACTOR was skipped, and each
  task was a single commit. Corrected mid-stream (ADR-0010, 3-commit RED/GREEN/REFACTOR)
  only after the user pushed on it. It should have been enforced from task 1.
- **Repeated RED-commit churn on line length.** The lint hook correctly blocked several
  RED commits on E501 (long test lines), costing a fix-and-retry loop ~6 times.
- **Beads closes silently reverted** to `in_progress` until we set `dolt.auto-commit=on`
  — the ledger was briefly wrong twice before we caught it.
- **Branch confusion.** Building on a `build/mvp` branch while GitHub showed `master`
  created a real "why isn't anything landing?" moment. Resolved by working on `master`.
- **CI mislabeled.** I called the Actions block "billing"; it was the private-repo quota.
  I over-trusted GitHub's own error wording over the user's account context.
- **We shipped a real bug** (`.36`, silent reviewer-skip) that violates our *own* "no
  silent truncation" principle — caught only by dogfooding, not by tests or review.
- **Token-frugality intent unrealized.** We build the `.prism/` workspace (per-file
  patches + shared context) but reviewers receive patches **embedded in the prompt**, so
  we don't get the article's 7×-savings. On a rate-limited subscription this matters more
  to us than it did to Cloudflare.

## What we can do better

- **Enforce TDD discipline + the 100-col limit from task 1.** Consider adding
  `ruff format` (auto-fix) to the pre-commit hook so formatting never blocks a RED commit.
- **Codify cross-cutting invariants** ("no silent truncation", "data not instructions",
  "stdin not argv", "what NOT to flag") as a short self-review checklist — the one we
  violated would have been caught.
- **Realize the workspace token-frugality** (reviewers read only their domain's patches).
- **Add the cheap reviewers** (performance, documentation, release) — the architecture was
  built for it; high fidelity-per-effort.
- **Decide a cloud-CI strategy** (accept local-only, public mirror, or self-hosted runner)
  rather than leaving red runs.

## Pivots to consider

None are forced — the core architecture is sound — but three are worth a deliberate look:

1. **Context strategy: embed-in-prompt → read-from-workspace.** The biggest fidelity +
   rate-limit win. Reviewers (agentic CLIs) read only relevant `.prism/patches/*`.
2. **Let the coordinator read source to verify** uncertain findings (the CLIs can; we
   don't wire it). Improves the judge's accuracy, matches the article.
3. **Risk tiers** to scale reviewers/effort by diff size & sensitivity (cost/rate budget).

Not pivoting: coordinator-as-judge (ADR-0008) is working well; no need to switch to
coordinator-driven spawn yet. API fallback (ADR-0001) stays deferred until rate limits bite.

## ADR assessment — do we need new ADRs now?

**No new ADR is strictly required right now** — decisions 0001–0010 cover the system as
built. Three decisions *will* need an ADR when we act on them:

- **Token-frugality / context-passing strategy** — when we change embed→workspace-read
  (pivot #1). This is genuinely architectural; write the ADR with the change.
- **Risk-tier policy** — when tiers are added (selection + model/effort scaling rules).
- **Decision severity ordering + `policy.fail_on` semantics** — small, surfaced by `.37`.
  Either a brief ADR-0011 or an inline decision when fixing it; lean ADR since it changes
  the public policy contract ("fail at this severity *or worse*").

**Optional now:** a lightweight ADR codifying the cross-cutting invariants as *enforced*
principles, given we just shipped a violation of one. Cheap insurance against recurrence.

## Addendum — real-repo validation (external, anonymized)

Ran Prism (local mode, full tier) against **one merged, already-human-reviewed change
(~200 lines, ~5 files) in an unrelated private repository** as a real-world data point.
Kept deliberately general — the repo and findings are private:

- **Decision: `minor_issues`** (did not block) — calibrated, not noisy.
- **2 warnings, 0 critical, 0 false positives, 0 style/nitpick noise.**
- One warning identified a **subtle interaction between two changes in the same diff**
  (one silently undermines the other) — a cross-cutting issue easy for humans to miss,
  and which had **already passed human review and merged**.
- The other was a security-adjacent observation raised with **nuance**: rather than
  over-escalating to "critical," the coordinator reasoned about likely *inherited*
  authorization and downgraded it to "verify this," with a concrete check + test to add.

**Takeaway:** the review-quality thesis (specialized reviewers + what-NOT-to-flag + a
calibrated judge pass) holds on an external codebase, not just our own — low noise, no
hallucinations, and a genuinely useful catch on already-merged code.

## Action items (tracked in beads)

- Fix self-review bugs: `.36` (silent skip), `.37` (exit-code ordering — likely ADR-0011).
- Fidelity roadmap (prioritized): more reviewers → workspace token-frugality → risk tiers
  → telemetry → re-review → resilience/control-plane → break-glass → GitLab.
- Open hardening: `.33` (read-only/temp-copy cred mounts), `.32` (missing-prompt hard-fail).
