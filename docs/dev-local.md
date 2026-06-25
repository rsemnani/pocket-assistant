# Local development (`@dev-pc`)

The fast inner loop. Everything runs locally with **mocked** integrations — no real LLM,
Gmail, Calendar, GitHub, or Claude Code calls, and no secrets required.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or see their install docs)
- Docker (optional; only needed for the full Postgres-backed stack)

## Backend, no database server (unit/contract tests)

Tests use an in-memory SQLite database via portable SQLAlchemy types, so no Postgres is
required.

```bash
cd backend
cp .env.example .env
uv sync
uv run pytest -q
```

## Backend, running the API locally

```bash
cd backend
uv run uvicorn pocket.api.main:app --reload
# Health check:
curl http://127.0.0.1:8000/v1/healthz
```

With the default `.env` (`LLM_PROVIDER=mock`, `DATABASE_URL` pointing at SQLite), the API
boots with deterministic mock adapters. Interpretation returns canned structured proposals
so you can exercise the full capture → propose → approve loop offline.

## Full stack with Postgres (matches production shape)

```bash
cd deploy
docker compose up --build
# API on http://127.0.0.1:8000 ; Postgres + Redis in containers.
```

Run migrations inside the API container (after reviewing them):

```bash
docker compose exec api uv run alembic upgrade head
```

## Linting / typing / security locally

```bash
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run bandit -r src
uv run pip-audit
```

## Pre-commit

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```
