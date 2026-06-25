# Backend image. Uses uv for fast, reproducible installs. Runs as a non-root user.
FROM python:3.14-slim AS base

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

# Drop privileges.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "pocket.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
