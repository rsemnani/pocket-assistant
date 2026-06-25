# Pocket Assistant — Backend

FastAPI backend with mocked integrations (Phase 1). Runs fully offline; no secrets required.

## Run

```bash
cp .env.example .env
uv sync --all-extras
uv run pytest -q
uv run uvicorn pocket.api.main:app --reload   # http://127.0.0.1:8000/v1/healthz
```

## Layout

```
src/pocket/
  core/          config, logging (redacted), security, idempotency, errors
  db/            models (portable types), session, enums, migrations
  schemas/       API schemas + canonical LLM action contract
  integrations/  Protocol interfaces + mock adapters + registry
  domain/        policy, interpret, execute, tasks, summary, audit
  api/           FastAPI app + routers + auth deps
  media/         filesystem media store (50 GB cap + prune)
  workers/       reminder/escalation scan
migrations/      Alembic (0001 baseline)
tests/           unit + integration (in-memory SQLite)
```

## Notes

- All integrations default to **mock** (`LLM_PROVIDER=mock`, etc.).
- Tests use in-memory SQLite via portable column types; production uses Postgres.
- Every LLM-proposed action requires approval; `pin_required` actions also need a session
  token from `POST /v1/devices/session/pin`.
