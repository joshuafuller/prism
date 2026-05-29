# 0004. GitHub-first via the `gh` CLI behind a VCS abstraction

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

The original design was GitLab-first (work environment). The owner will actually *test*
Prism against GitHub on a personal account, and starting there sidesteps the
subscription-auth-in-CI problem for now. We still want GitLab as a first-class target
later, so the core must not depend on any one provider. The host already has `gh`
authenticated as the personal account `joshuafuller`.

## Decision

We will define a `VCSProvider` interface (read PR/MR context, post findings) and ship a
**GitHub** implementation first that **shells out to the `gh` CLI**, reusing the host's
existing personal-account login. GitLab becomes a later implementation behind the same
interface. Prism verifies `gh auth status` resolves to the expected account before
posting. The core orchestration depends only on `VCSProvider`, never on GitHub specifics.

## Consequences

- Reuses existing `gh` auth (no separate PAT to manage); VCS calls are plain API and
  cost nothing against subscriptions.
- Consistent with the CLI-first philosophy of ADR-0001/0002.
- The provider seam keeps GitLab (and the work use-case) a drop-in addition, not a fork.
- Trade-off: depends on `gh` being installed/authed in the image; mitigated by bundling
  `gh` and an explicit auth precheck.
- Reversible: swapping `gh` for a library (`PyGithub`) is internal to the GitHub provider.
