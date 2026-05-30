# Agent Instructions

This project tracks work in **GitHub Issues**.

## Quick Reference

```bash
gh issue list                                  # open work
gh issue view <n>                              # details
gh issue create --title "..." --body "..."     # file follow-ups
```

Use GitHub Issues for task tracking — not TodoWrite or markdown TODO lists. File an issue
before starting non-trivial work and reference it in commits/PRs.

> Previously tracked with beads (`bd`); the `.beads/` files remain as a historical export
> and are no longer the source of truth.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

## Session Completion

Work is **not** complete until `git push` succeeds:

1. File GitHub Issues for any remaining/follow-up work.
2. Run quality gates (tests, ruff, mypy) if code changed.
3. Close finished issues; comment on in-progress ones.
4. `git pull --rebase && git push`, then confirm `git status` shows "up to date with origin".
