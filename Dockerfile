# Prism runs natively in Docker. Subscription credentials are mounted at runtime
# (see bin/prism) into /home/app, so no secrets are ever baked into the image.
FROM python:3.12-slim

# System deps + Node (for the claude/codex CLIs) + gh + bubblewrap (codex sandbox).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates gnupg bubblewrap \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Subscription CLIs (model versions resolve from the mounted subscription at runtime).
RUN npm install -g @anthropic-ai/claude-code @openai/codex

# uv (no pip).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Non-root user. APP_UID should match the host user so mounted creds are readable
# (default 1000; override: docker build --build-arg APP_UID="$(id -u)").
ARG APP_UID=1000
RUN useradd -m -u "${APP_UID}" -d /home/app app
USER app
ENV HOME=/home/app

# Install the app into its own dir; reviews run against the mounted repo at /repo.
WORKDIR /app
COPY --chown=app:app . /app
RUN uv sync --no-dev

WORKDIR /repo
# --no-dev --frozen: run from the locked runtime env; never fetch dev tooling at runtime.
ENTRYPOINT ["uv", "run", "--project", "/app", "--no-dev", "--frozen", "prism"]
