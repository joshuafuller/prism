# 0002. Native Docker packaging with mounted subscription credentials

- **Date:** 2026-05-29
- **Status:** Accepted

## Context

Prism must run natively in Docker (portability, reproducibility, and a path to CI). But
the cost model from ADR-0001 depends on subscription CLIs, which authenticate via
interactive OAuth tied to local config. Whether that auth survives inside an ephemeral
container — without re-login and without silently falling back to a billed API key — was
the single assumption the entire "$0 in Docker" premise rested on. Getting this wrong
would collapse the cost model and force a user-level fork (host execution vs. API billing).

## Decision

We will package Prism as a **native Docker image** (`python + uv + claude CLI +
codex CLI + gh CLI + bubblewrap`) and supply subscription credentials by **mounting the
host credential files** into the container:
`~/.claude/.credentials.json` + `~/.claude.json`, `~/.codex/auth.json` + `config.toml`,
and `~/.config/gh` for VCS auth. We proved this works before adopting it (see below).

## Consequences

- **Keystone proven 2026-05-29:** with a minimal image, creds mounted, and **no API key
  in the environment**, `claude -p` and `codex exec` both returned answers — so success
  can only be subscription-backed. Credentials are file-based (not keyring), so directory
  mounts carry them.
- Operational constraints captured: container `$HOME` must match the mount target
  (UID alignment for a non-root `app` user); install `bubblewrap` for the Codex sandbox;
  pass `codex --skip-git-repo-check` for non-git workspaces.
- CI later is easier (already containerized), though ephemeral-runner auth remains a
  separate, deferred problem.
- Risk: token refresh writes to mounted files; mount real creds read-write in normal use,
  but test only against **copies** so experiments cannot corrupt host auth.
- Reversible fallback (now moot): run on host, or use the ADR-0001 API path.
