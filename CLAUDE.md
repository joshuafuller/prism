# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

## Issue Tracking

This project tracks work in **GitHub Issues**.

```bash
gh issue list                                  # open work
gh issue view <n>                              # details
gh issue create --title "..." --body "..."     # file follow-ups
```

- Use GitHub Issues for task tracking — do NOT use TodoWrite or markdown TODO lists.
- File an issue before starting non-trivial work and reference it in commits/PRs.

> The project previously used beads (`bd`). The `.beads/` files remain as a historical
> export and are no longer the source of truth.

## Session Completion

When ending a work session, work is **not** complete until `git push` succeeds:

1. File GitHub Issues for any remaining/follow-up work.
2. Run quality gates (tests, ruff, mypy) if code changed.
3. Update issue status — close finished work, comment on in-progress items.
4. **Push to remote:**
   ```bash
   git pull --rebase
   git push
   git status   # MUST show "up to date with origin"
   ```
5. Verify everything is committed AND pushed.


## Build & Test

_Add your build and test commands here_

```bash
# Example:
# npm install
# npm test
```

## Architecture Overview

_Add a brief overview of your project architecture_

## Conventions & Patterns

_Add your project-specific conventions here_
