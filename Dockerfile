# syntax=docker/dockerfile:1
# Prism runs natively in Docker on a Chainguard wolfi base — small and low-CVE.
# Credentials are mounted at runtime (see bin/prism) into /home/app; nothing secret
# is ever baked into the image.

###############################################################################
# Stage 1 — build the locked Python venv with uv. Isolated so uv and the build
# cache never reach the final image, and so a code change doesn't re-resolve the
# dependency layer.
###############################################################################
FROM cgr.dev/chainguard/wolfi-base AS pybuild

RUN apk add --no-cache python-3.12
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Use the base image's own interpreter (never download a second one) and build the
# venv at a fixed path so it works unchanged when copied into the runtime stage.
ENV UV_PYTHON=/usr/bin/python3.12 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
# Resolve dependencies first (cached unless pyproject/lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project
# Then install the application itself.
COPY . .
RUN uv sync --no-dev --frozen

###############################################################################
# Stage 2 — runtime. Python + Node + the subscription CLIs + gh/git/bubblewrap.
###############################################################################
FROM cgr.dev/chainguard/wolfi-base AS runtime

# The claude/codex CLIs are Node apps; codex sandboxes with bubblewrap on Linux.
RUN apk add --no-cache \
        python-3.12 nodejs npm git gh bubblewrap ca-certificates-bundle posix-libc-utils \
    && npm install -g @anthropic-ai/claude-code @openai/codex \
    && npm cache clean --force \
    && rm -rf /root/.npm /tmp/*

# Non-root user; APP_UID should match the host user so mounted creds are readable
# (default 1000; override: docker build --build-arg APP_UID="$(id -u)").
ARG APP_UID=1000
RUN adduser -D -u "${APP_UID}" -h /home/app app

# The locked venv + app, built in stage 1. No uv, no build tools in this image.
COPY --from=pybuild --chown=app:app /app /app

USER app
ENV HOME=/home/app
WORKDIR /repo
# Launch the console script straight from the venv — no `uv run` at runtime.
ENTRYPOINT ["/app/.venv/bin/prism"]
