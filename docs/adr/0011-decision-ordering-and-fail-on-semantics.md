# 0011. Decision severity ordering and `policy.fail_on` semantics

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

`policy.fail_on` controls when a review fails CI (nonzero exit). The field name reads as
"fail at this severity **or worse**", but the MVP implementation compared with identity
(`result.decision is config.policy.fail_on`). That is correct only because the default
`fail_on` (`significant_concerns`) is already the most severe outcome. With a stricter
threshold (e.g. `minor_issues`), a *more* severe verdict like `significant_concerns` would
**not** fail CI — a silent gap. Prism found this in its own code (prism-4gf.37). `Decision`
is a `StrEnum`, so default comparison is alphabetical and meaningless for severity.

## Decision

`Decision` gains an explicit **severity ordering**:

```
approved (0) < approved_with_comments (1) < minor_issues (2) < significant_concerns (3)
```

exposed as a `rank` property and an `at_least(other)` helper. `policy.fail_on` means
**"fail when the decision is at least as severe as this"**: CI fails iff
`result.decision.at_least(config.policy.fail_on)`. The existing `blocks` property is kept
(it is exactly `at_least(SIGNIFICANT_CONCERNS)`).

## Consequences

- `fail_on` behaves as its name implies for *any* threshold, not just the default.
- Severity ordering is defined once and reusable (e.g. future report sorting, gating).
- We deliberately do **not** make `Decision` rich-comparable via `<`/`>=` operators
  (it is a `StrEnum`; overriding string comparison invites subtle bugs). Ordering is
  explicit via `rank`/`at_least`.
