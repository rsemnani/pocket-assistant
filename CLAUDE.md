# CLAUDE.md — Pocket Assistant

Context for any Claude Code session working on this repo. Read this first; it lets a fresh
session be productive without re-deriving the project. Deeper detail lives in
[`DESIGN.md`](./DESIGN.md) and [`docs/`](./docs).

## What this is

A voice-capture personal assistant. A retired **Nextbit Robin** Android phone (kiosk-style
app) captures speech → transcribes on-device (Vosk) → sends to a self-hosted **FastAPI**
backend that uses an LLM (**Claude-first**, behind an abstraction) to interpret commands and
propose **structured, approval-gated actions** (tasks, reminders, ICS events, Gmail
searches, GitHub issues, Claude Code jobs).

## Monorepo layout

```
android/    Kotlin + Jetpack Compose kiosk client (minSdk 24, compileSdk 34)
backend/    FastAPI API + workers + integrations (all integrations have mocks)
deploy/     Docker Compose stack (api + postgres + redis) for the home server
shared/     Canonical action-schema notes shared by app + backend
docs/       dev-local / deploy-mini / android-testing / security / runbooks
scripts/    fetch-vosk-model.sh, sync-to-mini.sh, dev helpers
DESIGN.md   Full technical design (25 sections) — the source of truth
```

## Execution contexts (always be explicit about which one)

- **@dev-pc** — the computer the Robin is plugged into via USB. Android builds + `adb` happen
  here. Toolchain env: `source android/.build-env.sh` (git-ignored; sets JAVA_HOME/ANDROID_HOME).
- **@mini** — the home server, `ssh rs@nucboxk8plus` (lands in WSL). Backend, Postgres,
  workers, media live here. Deploy = `git pull` + `docker compose up -d --build` in `deploy/`.
- **@docker** — the containers on @mini.

## Commands

Backend (from `backend/`, uses a local `.venv` here or `uv` in CI/Docker):
```bash
.venv/bin/python -m pytest -q          # tests (in-memory SQLite, no services needed)
.venv/bin/python -m ruff check src tests && .venv/bin/python -m mypy src
.venv/bin/python -m bandit -q -r src
```
Android (from `android/`):
```bash
source .build-env.sh
./gradlew :app:assembleDebug           # build
./gradlew :app:installDebug            # build + install to the connected Robin
adb logcat | grep -i pocket            # logs
```
First time: `./scripts/fetch-vosk-model.sh` (downloads the ~40 MB model, not committed).

## Architectural rules (do not break these)

- **The LLM proposes; the backend disposes.** The model only emits proposals matching the
  action schema (`backend/src/pocket/schemas/actions.py`). It never executes anything.
- **Sensitivity is assigned server-side** (`domain/policy.py`), never trusted from the LLM.
  Tiers: `normal` / `approval` / `pin_required`. `pin_required` needs a PIN-unlocked session.
- **All DB access is via SQLAlchemy ORM** — no raw SQL string-building (SQLi guard).
- **Idempotency** on resource-creating endpoints (`Idempotency-Key`).
- **Migrations** via Alembic — never edit schema ad hoc.
- **Structured logs never contain** transcripts, email bodies, or raw LLM I/O (redaction in
  `core/logging.py`). Reference sensitive content by ID.
- **Tasks are only marked done explicitly** — never auto-complete.

## Security / public-repo rules (mandatory)

- The repo is **public**. Never commit secrets, tokens, real hostnames, IPs, audio,
  transcripts, generated ICS, or `.env` (only `*.env.example`). Gitleaks runs in CI +
  pre-commit.
- Real secrets live in `deploy/.env` on @mini and `android/.build-env.sh` on @dev-pc (both
  git-ignored). Deploy/runtime values are not in the repo by design.
- Least privilege: Gmail read-only + draft-only (no send), GitHub fine-grained + repo
  allowlist, calendar via a single private iCal feed (no OAuth).

## Deployment shape (no secrets here)

Backend runs on @mini via Docker Compose, bound to **localhost only**, exposed through an
existing **Cloudflare tunnel** (token-managed, host-networked). The public hostname + port
are configured in `deploy/.env` and entered per-device in the app's Settings — not committed.
LLM provider currently `mock`; real Claude is gated behind an API key + approval.

## Working an issue (the per-issue workflow)

This project is built to be worked **one issue per session** (see
[`CONTRIBUTING.md`](./CONTRIBUTING.md)):

1. Pick a GitHub issue. Branch: `git switch -c <type>/<issue#>-<slug>` (type = fix/feat/chore).
2. Make the change; keep the quality gate green (ruff + mypy + bandit + pytest for backend).
3. Open a PR that says `Closes #<issue>`. CI must pass.
4. For changes that affect the running backend, redeploy to @mini (with approval).

Keep changes scoped to the issue. If you discover adjacent work, file a new issue rather than
expanding scope.

## Status

Phases 0–2 done (design, backend with mocks, Android client) and deployed. Next: real Claude
(Phase 4), reminders/escalation worker + proactive morning summary (Phase 3), integrations
(Phase 5), Claude Code automation (Phase 6). See [`DESIGN.md` §24](./DESIGN.md).
