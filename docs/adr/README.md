# Architecture Decision Records

Critical, architecturally-significant, or hard-to-reverse decisions are recorded here
as ADRs. **Forcing an ADR is mandatory before locking any critical decision** during
design.

Format: lightweight Nygard (Context / Decision / Consequences). Use `template.md`.
Number sequentially. Status is one of: Proposed | Accepted | Superseded by ADR-N |
Deprecated.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-subscription-cli-first-runtime.md) | Subscription-CLI-first runtime, API-key fallback | Accepted |
| [0002](0002-native-docker-credential-mount-auth.md) | Native Docker packaging with mounted subscription credentials | Accepted |
| [0003](0003-python-uv-tooling.md) | Python + uv (no pip / no manual venvs) | Accepted |
| [0004](0004-github-first-via-gh-cli.md) | GitHub-first via the `gh` CLI behind a VCS abstraction | Accepted |
| [0005](0005-beads-work-tracking.md) | Beads (`bd`) as the work-tracking system of record | Accepted |
| [0006](0006-reasoning-effort-routing-knob.md) | Reasoning effort as a first-class routing knob | Accepted |
| [0007](0007-runtime-divergence-from-opencode.md) | Runtime: subscription CLIs replace OpenCode | Accepted |
| [0008](0008-orchestration-pluggable-seam.md) | Orchestration is a pluggable seam; MVP ships simplest strategy | Accepted |
| [0009](0009-markdown-agent-prompts.md) | Agent prompts in markdown + shared rules file | Accepted |
| [0010](0010-mandatory-tdd-red-green-refactor.md) | Mandatory Red-Green-Refactor with per-stage commits | Accepted |
| [0011](0011-decision-ordering-and-fail-on-semantics.md) | Decision severity ordering and `policy.fail_on` semantics | Accepted |
| [0012](0012-enforced-cross-cutting-invariants.md) | Enforced cross-cutting invariants | Accepted |
| [0013](0013-risk-tiers.md) | Risk tiers — scale reviewers/effort by diff | Accepted |
| [0014](0014-ast-based-risk-escalation.md) | AST-based risk escalation | Accepted |
