# Pocket Assistant

Turn a retired Android phone (a Nextbit Robin) into a dedicated, appliance-like
**voice-capture personal assistant**. Wake the screen, press and hold a big button, speak,
review/edit the transcript, and send it to a self-hosted backend. The backend uses an LLM
(**Claude first**, behind a provider abstraction) to interpret commands and propose
**structured, approval-gated actions**: tasks, reminders, calendar events (ICS), Gmail
searches, GitHub issues, and Claude Code job prompts.

> **Design source of truth:** see [`DESIGN.md`](./DESIGN.md). This README is the quick start;
> DESIGN.md is the full build plan.

## Core principles

- **Capture is cheap; action is deliberate.** Anything that changes the outside world
  requires explicit approval; the most sensitive actions also require a session PIN.
- **The LLM proposes; the backend disposes.** The model only emits validated proposals — it
  never mutates external systems directly.
- **Privacy-first.** Offline transcription preferred; transcripts/audio never enter git;
  least-privilege integration scopes; logs never contain raw transcript/email content.
- **Public-repo-safe from day one.** No secrets in git; secret scanning in CI and
  pre-commit.

## Monorepo layout

```
android/    Kotlin + Jetpack Compose kiosk capture app   (Phase 2)
backend/    FastAPI API + workers + integrations (mocked) (Phase 1)
shared/     Canonical action schema shared by app + backend
deploy/     Docker Compose stack for the home server
docs/       Dev / deploy / security / Android-testing docs
scripts/    Dev + deploy helper scripts
```

## Execution contexts

The project spans three machines — see [`docs/`](./docs) for details:

- **`@dev-pc`** — the computer the phone is plugged into (Android builds, ADB).
- **`@mini`** — the home server (`ssh rs@nucboxk8plus`, lands in WSL); runs the backend, DB,
  workers, media.
- **`@docker`** — containers on `@mini` orchestrated by Docker Compose.

## Quick start (backend, local, mocked integrations)

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). No secrets or external services
needed — all integrations default to **mock**.

```bash
cd backend
cp .env.example .env          # defaults are safe: LLM_PROVIDER=mock, SQLite test DB
uv sync                       # install locked dependencies
uv run pytest                 # run the test suite
uv run uvicorn pocket.api.main:app --reload   # http://127.0.0.1:8000/v1/healthz
```

See [`docs/dev-local.md`](./docs/dev-local.md) for the full local loop and
[`docs/deploy-mini.md`](./docs/deploy-mini.md) for deploying to the home server.

## Status

- ✅ Phase 0 — repo + safety scaffolding
- 🚧 Phase 1 — backend core with mocked integrations
- ⬜ Phase 2 — Android capture client
- ⬜ Phases 3–7 — tasks/reminders, real LLM, integrations, Claude Code, hardening

See [`DESIGN.md` §24](./DESIGN.md#24-recommended-implementation-phases) for the phase plan.

## Security

No secrets are ever committed. Local secrets live in `.env` (git-ignored); only
`.env.example` placeholders are committed. See [`docs/security.md`](./docs/security.md) and
the [secret-rotation runbook](./docs/runbooks/secret-rotation.md).

## License

[MIT](./LICENSE).
