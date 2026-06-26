# Backend image. Uses uv for fast, reproducible installs. Runs as a non-root user.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

# uv from the official distroless image (pinned by tag; Dependabot updates it).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml ./
RUN uv sync --extra postgres --no-install-project --no-dev

# Copy source and install the project.
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --extra postgres --no-dev

# Optionally install Node + the Claude CLI for the `claude_cli` LLM provider (subscription
# auth). Off by default so CI/default builds stay lean; the deploy build sets it to "true".
ARG INSTALL_CLAUDE_CLI=false
ARG NODE_VERSION=20.18.1
RUN if [ "$INSTALL_CLAUDE_CLI" = "true" ]; then \
      set -eux; \
      apt-get update; \
      apt-get install -y --no-install-recommends curl ca-certificates xz-utils; \
      arch="$(dpkg --print-architecture)"; \
      case "$arch" in amd64) nodearch=x64 ;; arm64) nodearch=arm64 ;; *) echo "unsupported arch $arch"; exit 1 ;; esac; \
      curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${nodearch}.tar.xz" -o /tmp/node.tar.xz; \
      tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1; \
      rm /tmp/node.tar.xz; \
      npm install -g @anthropic-ai/claude-code; \
      claude --version; \
      apt-get purge -y curl xz-utils; apt-get autoremove -y; rm -rf /var/lib/apt/lists/*; \
    fi

# Drop privileges.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "pocket.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
