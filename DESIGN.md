# Pocket Assistant — Technical Design Document

> **Status:** Design only. No code, credentials, external API calls, remote changes, or
> migrations have been created as part of this document. This is the build plan for a
> future monorepo.
>
> **Document version:** 0.1 (initial design)
> **Last updated:** 2026-06-25

---

## Table of Contents

1. [Product Summary](#1-product-summary)
2. [User Flows](#2-user-flows)
3. [System Architecture](#3-system-architecture)
4. [Current-Computer vs Mini-Computer/WSL Workflow](#4-current-computer-vs-mini-computerwsl-workflow)
5. [Android App Design](#5-android-app-design)
6. [Backend Design](#6-backend-design)
7. [Database Schema Proposal](#7-database-schema-proposal)
8. [Media/Audio Storage Design](#8-mediaaudio-storage-design)
9. [LLM / Tool-Calling Design](#9-llm--tool-calling-design)
10. [Gmail Integration Design](#10-gmail-integration-design)
11. [Calendar / ICS Integration Design](#11-calendar--ics-integration-design)
12. [GitHub / Claude Code Automation Design](#12-github--claude-code-automation-design)
13. [Security and Approval Model](#13-security-and-approval-model)
14. [Public GitHub Repository Safety Model](#14-public-github-repository-safety-model)
15. [Secret-Management Strategy](#15-secret-management-strategy)
16. [Dependency / Vulnerability-Management Strategy](#16-dependency--vulnerability-management-strategy)
17. [CI / Security-Check Strategy](#17-ci--security-check-strategy)
18. [Audit Logging Model](#18-audit-logging-model)
19. [Task / Reminder Behavior](#19-task--reminder-behavior)
20. [Daily Summary Behavior](#20-daily-summary-behavior)
21. [MVP Scope](#21-mvp-scope)
22. [Non-MVP Future Features](#22-non-mvp-future-features)
23. [Open Questions](#23-open-questions)
24. [Recommended Implementation Phases](#24-recommended-implementation-phases)
25. [Initial Repo Structure](#25-initial-repo-structure)

---

## Conventions & Design Assumptions

Throughout this document, items marked **[ASSUMPTION]** are defaults chosen where the
brief was unclear. They are safe-by-default and can be changed later. Items marked
**[DECISION]** are recommended technical choices with rationale.

Three execution contexts are referenced consistently:

- **`@dev-pc`** — the *current computer* the Nextbit Robin is physically connected to via
  USB. This is where Android builds, ADB, and APK installs happen.
- **`@mini`** — the *mini computer / NucBox* home server, reached with
  `ssh rs@nucboxk8plus`, which lands in a **WSL** shell on Windows. The backend, database,
  workers, and media storage live here.
- **`@docker`** — Docker containers running on `@mini` (orchestrated by Docker Compose).
  The backend, Postgres, workers, etc. run inside these containers.

When a step must run in a specific context, it is labeled with one of these tags.

---

## 1. Product Summary

**Pocket Assistant** turns a retired Nextbit Robin Android phone into a dedicated,
appliance-like voice-capture device for a personal assistant system. The phone is treated
as a **kiosk-style device**, not a general phone app: wake the screen, press the big
button, speak, review/edit the transcript, send.

The phone is a **thin capture-and-confirm client**. All intelligence (LLM interpretation,
task management, integrations) lives in a backend on the home server. The backend uses an
LLM — **Claude first**, behind a provider abstraction — to interpret commands and propose
**structured actions**: tasks, reminders, calendar events (as ICS for MVP), Gmail searches,
GitHub issues, and Claude Code job prompts.

### Core principles

1. **Capture is cheap; action is deliberate.** Voice capture is frictionless. Anything
   that changes the outside world (email, calendar, code, GitHub) requires explicit
   approval, and the most sensitive actions require a session PIN.
2. **The LLM proposes; the backend disposes.** The LLM never directly mutates external
   systems. It emits structured proposals that the backend validates against a schema and
   then executes only after approval.
3. **Privacy-first.** Offline transcription preferred. Transcripts and audio never enter
   git. Least-privilege scopes for Gmail/Calendar/GitHub. Structured logs never contain
   raw transcript/email bodies.
4. **Public-repo-safe from day one.** The repository is designed to be public; no secrets,
   no machine-specific details, secret scanning in CI.
5. **Practical MVP over grand architecture.** Ship a working capture → interpret →
   approve → act loop with a small set of commands, then expand.

### What the MVP delivers

- A kiosk Android app: wake → hold-to-record → on-device transcription → editable
  transcript with a 5-second auto-send countdown → Send/Edit/Cancel.
- A FastAPI backend on `@mini` (Docker Compose) with Postgres, a worker, and file-based
  media storage capped at 50 GB.
- LLM interpretation producing validated action proposals, all requiring approval.
- An internal task system with priority escalation and bounded reminders.
- Three flagship commands: "What's my day look like?", "Did anyone get back to me?",
  and the day-trader-site GitHub-issue + Claude Code flow.
- Full audit logging of transcripts, interpretations, tool calls, approvals, and outcomes.

---

## 2. User Flows

### 2.1 Voice capture (primary loop)

```
[Pick up phone] → [Wake screen] → App is foreground (kiosk)
   → [Press & HOLD big button]
       → start sound + vibrate
       → record audio (16 kHz mono PCM/WAV)
   → [Release button]
       → stop sound + vibrate
       → on-device transcription (Vosk)
   → [Editable transcript screen]
       → 5-second countdown ring begins
       → user options:
           • Send (immediate)
           • Edit (cancels countdown; keyboard opens)
           • Cancel (discards capture + audio)
       → if countdown reaches 0 with no interaction → auto-Send
   → [Upload to backend]: audio + transcript + metadata + idempotency key
   → [Backend interprets] → returns proposed actions
   → [Proposal review screen on phone]
       → assistant explains what it will do
       → user Approves / Rejects each action
       → if action is "sensitive" → session PIN required (once per session window)
   → [Backend executes approved actions] → results shown + optionally spoken
```

**[DECISION] Press-and-hold for MVP** (not tap-start/tap-stop). Rationale: it is
unambiguous (recording == finger down), avoids "did I forget to stop?" dangling
recordings, and is the most appliance-like. A tap-to-toggle mode can be added later as a
setting for long dictations. An **accessibility fallback** (tap-start/tap-stop) will be
included behind a setting because press-and-hold is hard for some users; MVP defaults to
hold.

### 2.2 "What's my day look like?" (read-only, auto-approvable later)

```
Speak → transcript → backend classifies intent = DAILY_SUMMARY
   → backend assembles: calendar events (from synced/ICS state),
     active/scheduled tasks, overdue-not-done tasks, reminders,
     optional important email follow-ups (only if relevant)
   → returns summary text + structured cards
   → phone DISPLAYS and SPEAKS (TTS) the summary
   → assistant asks: "Did you finish <overdue/high-priority task>?"
       → user answers → task status updated only on explicit confirmation
```

This is **read-only** and is a candidate for auto-approval after development hardening.
It also fires **proactively** every morning on first screen-wake (see §20).

### 2.3 "Did anyone get back to me?" (limited email read)

```
Speak → intent = EMAIL_FOLLOWUP
   → backend default window = last 1 day [ASSUMPTION], job/task-related focus
   → Gmail search (read-only scope) → candidate threads
   → backend summarizes candidates (sender, subject, 1-line gist)
   → phone shows summary; "Want me to look deeper into any of these?"
   → NO deeper action (open attachment, draft) without explicit approval
```

The assistant **never** searches all mail freely; the window and intent constrain it.
Broad searches require explicit instruction + session PIN.

### 2.4 Day-trader site issue → GitHub issue + Claude Code job (sensitive)

```
Speak: "The day trader site has an issue pulling data from the DB.
        Create an issue and see if you can automatically fix it."
   → intent = CODE_TASK
   → backend resolves target repo:
       • if unambiguous → confirm with user
       • if ambiguous / multiple candidates → ASK with options (clarify)
   → proposes a bundle of actions:
       1. Create local task record
       2. Create GitHub issue (draft shown first)
       3. Prepare a Claude Code job prompt (shown first)
   → user approves the bundle (issue + task)
   → invoking Claude Code (code-affecting automation) requires:
       • explicit approval AND
       • session PIN/pattern confirmation
   → only after PIN → backend enqueues a Claude Code job
   → job runs in a sandboxed worker → produces a branch/PR/diff (never auto-merge)
   → result + link surfaced back to phone + audit log
```

### 2.5 Note capture with LLM routing

```
Speak: "Take a note: I should implement logging in the new website."
   → intent = NOTE (LLM decides best treatment)
   → LLM proposes one or more of: note, task, project idea,
     GitHub issue, Claude Code job — unless user dictated the type
   → proposal shown; user approves the chosen routing
   → stored in assistant DB (notes live in the same DB)
```

### 2.6 Device registration (one-time)

```
@dev-pc: build + install APK via ADB
   → app first run: shows pairing screen
   → user generates a device-registration code on backend (CLI or admin endpoint)
   → app exchanges code for a long-lived device token (stored in Android Keystore)
   → all subsequent API calls authenticated with device token
```

---

## 3. System Architecture

### 3.1 Component diagram (logical)

```
┌──────────────────────────────────────────────────────────────────┐
│  Nextbit Robin (Android, kiosk)            @phone                  │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │ Capture UI │→ │ Vosk STT     │→ │ Transcript review + send   │ │
│  │ (Compose)  │  │ (on-device)  │  │ Proposal review + approve  │ │
│  └────────────┘  └──────────────┘  └────────────────────────────┘ │
│        device token (Android Keystore), TTS, audio cache           │
└───────────────────────────────┬──────────────────────────────────┘
                                 │ HTTPS (Wi-Fi / remote)
                                 │ device-token auth
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│  Mini computer (Windows + WSL)              @mini                  │
│  Docker Compose stack                       @docker                │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────────┐   │
│  │ FastAPI API   │  │ Worker(s)     │  │ Postgres (operational)│  │
│  │ - auth        │  │ - reminders   │  │ tasks/notes/audit/... │  │
│  │ - upload      │  │ - escalation  │  └──────────────────────┘   │
│  │ - transcript  │  │ - LLM jobs    │  ┌──────────────────────┐   │
│  │ - proposals   │  │ - integ. jobs │  │ Redis (queue/cache)   │  │
│  │ - approvals   │  │ - CC jobs     │  └──────────────────────┘   │
│  └───────┬───────┘  └───────┬───────┘  ┌──────────────────────┐   │
│          │                  │          │ Media store (files)   │   │
│          │                  │          │ /data/media ≤ 50 GB   │   │
│          ▼                  ▼          └──────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Integration layer (interfaces + adapters)                 │    │
│  │  LLM(Claude|OpenAI) · Gmail · Calendar/ICS · GitHub · CC  │    │
│  │  every adapter has a MOCK implementation for dev/test     │    │
│  └──────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬──────────────────────────────────┘
                                 │ outbound, least-privilege
          ┌──────────────────────┼───────────────────────┐
          ▼                      ▼                        ▼
   Anthropic / OpenAI      Gmail / Calendar API      GitHub API / Claude Code
   (LLM interpretation)    (read-mostly scopes)      (issues, code jobs)
```

### 3.2 Request lifecycle (capture → action)

1. **Capture** (`@phone`): record → transcribe → user edits → POST audio + transcript.
2. **Ingest** (`@docker` API): validate, store media reference, persist transcript +
   metadata, write audit `CAPTURE_RECEIVED`.
3. **Interpret** (`@docker` worker): build a constrained prompt (task context only, unless
   email/calendar explicitly required), call LLM via provider abstraction, receive
   structured JSON, **validate against the action schema**, persist `Interpretation` +
   `ProposedAction` rows, audit `INTERPRETATION_CREATED`.
4. **Review** (`@phone`): GET proposed actions; assistant explains; user approves/rejects;
   sensitive actions gate on session PIN.
5. **Execute** (`@docker` worker): for each approved action, call the relevant adapter with
   **idempotency keys**, retry with backoff, audit each tool call + outcome.
6. **Report** (`@phone`): results displayed + optionally spoken.

### 3.3 Technology choices

| Layer | Choice | Rationale |
|---|---|---|
| Android UI | **Kotlin + Jetpack Compose** [DECISION] | Modern, Google-supported, less boilerplate; best long-term for a Compose-first kiosk UI. |
| On-device STT | **Vosk** [DECISION] | Offline, open-source, runs on old ARM hardware, English small model ~50 MB. |
| Backend | **Python 3.12 + FastAPI** [DECISION] | Fast to build, strong typing via Pydantic, excellent for LLM/tool orchestration, easy mocking, huge ecosystem. |
| DB | **PostgreSQL 16** [DECISION] | Concurrent workers + API, JSONB for flexible proposal payloads, robust migrations. SQLite rejected: multi-process workers + API want a real server. |
| Queue | **Redis + RQ or Arq** [DECISION] | Lightweight job queue for workers; Arq is async-native (fits FastAPI). |
| ORM/migrations | **SQLAlchemy 2.x + Alembic** | Typed models, first-class migrations (no ad hoc schema edits). |
| Validation | **Pydantic v2** | Strong typing + input validation on every endpoint and every LLM output. |
| Container | **Docker + Docker Compose** | Matches deployment target; reproducible stack on `@mini`. |
| Media store | **Filesystem volume** (not DB) | Keeps operational DB fast; capped at 50 GB with lifecycle pruning. |
| Reverse proxy/TLS | **Caddy or Traefik** [DECISION] | Auto-TLS; terminate HTTPS in front of FastAPI. |

---

## 4. Current-Computer vs Mini-Computer/WSL Workflow

This section is deliberately explicit because three execution contexts are involved.

### 4.1 Context responsibility matrix

| Activity | Context | Notes |
|---|---|---|
| Build Android APK / AAB | `@dev-pc` | Gradle build on the computer the phone is plugged into. |
| ADB install / logcat / phone debugging | `@dev-pc` | Phone is physically connected here, **not** to `@mini`. |
| On-device transcription testing | `@dev-pc` → `@phone` | Run app, inspect via logcat. |
| Edit backend code | `@dev-pc` | Code authored locally; repo is the single source of truth. |
| Run backend stack | `@docker` on `@mini` | `docker compose up` inside WSL. |
| Database (Postgres) | `@docker` on `@mini` | Volume-backed; never on the phone, never only on `@dev-pc`. |
| Run migrations | `@docker` on `@mini` | Alembic inside the API container (after approval). |
| Media storage | `@mini` filesystem (mounted into `@docker`) | `/data/media`, 50 GB cap. |
| LLM / Gmail / Calendar / GitHub calls | `@docker` on `@mini` | Outbound from the server, using server-held secrets. |
| Claude Code jobs | `@docker` on `@mini` (sandboxed worker) | Code-affecting; gated by approval + PIN. |
| Secret-scan / CI | GitHub Actions (cloud) + local pre-commit on `@dev-pc` | |

### 4.2 Development loop

**Backend development (deploy/test remotely on `@mini`):**

Two supported modes — pick per task:

- **Mode A — Remote-run (recommended for integration):**
  1. `@dev-pc`: edit code, commit/push to a branch (or sync via `rsync`/`git pull` on
     `@mini`).
  2. `@mini`: `ssh rs@nucboxk8plus`, `cd` into repo in WSL, `docker compose up --build`.
  3. Test against the real stack; the phone (on `@dev-pc`) points at `@mini`'s API URL.
  4. **[ASSUMPTION]** Use a code sync helper script (e.g. `scripts/sync-to-mini.sh` using
     `rsync` over SSH, or just `git pull` on `@mini`) rather than editing on the server.
     Server is a deploy target, not an editor.

- **Mode B — Local-run (fast inner loop):**
  1. `@dev-pc`: run the backend locally in Docker for unit/contract tests with **mocked**
     integrations (no real LLM/Gmail/GitHub).
  2. Promote to Mode A for end-to-end checks.

**Android development:**
  1. `@dev-pc`: `./gradlew installDebug` (USB) to the connected Robin.
  2. App's backend base URL is **configurable** (build flavor / in-app dev setting), e.g.
     `http://<mini-lan-ip>:<port>` on LAN, or a stable remote hostname when away.
  3. Debug via `adb logcat`.

### 4.3 Networking between phone and server

- **On home LAN:** phone → `@mini` over Wi-Fi using the mini's LAN address and the API
  port. **[ASSUMPTION]** The LAN IP is treated as non-sensitive but is still kept out of
  committed config (use `.env` / in-app setting), per repo-safety rules.
- **Remote (phone on cellular/other Wi-Fi):** **[ASSUMPTION]** expose the backend via a
  secure tunnel rather than port-forwarding. Recommended: **Tailscale** (private mesh VPN,
  zero public exposure) [DECISION], or Cloudflare Tunnel if a public hostname with TLS is
  desired. The phone joins the tailnet and reaches `@mini` by its tailnet name. This avoids
  opening the home network and keeps the API off the public internet.
- All phone↔backend traffic is **HTTPS** with **device-token** auth regardless of path.

### 4.4 What Claude Code (the assistant building this) must confirm before doing

Per the safety rules, before any of the following, the assistant explains intent and asks
for approval:

- Pushing to GitHub.
- SSHing to `@mini` to change anything (`docker compose`, file writes).
- Creating credentials / OAuth clients.
- Running Alembic migrations against any real DB.
- Calling any external API (LLM/Gmail/Calendar/GitHub).
- Invoking Claude Code code-modifying jobs.

---

## 5. Android App Design

### 5.1 Goals & non-goals

- **Goal:** a dependable, large-target, single-purpose capture appliance usable
  immediately after screen wake.
- **MVP non-goal:** a true lock-screen overlay or power-button/Siri-style activation.
  Designed for later (see §22), **not required** for MVP. MVP assumes the app is the
  foreground/kiosk app after wake.

### 5.2 Kiosk strategy (MVP)

**[DECISION]** Use Android's built-in **Lock Task / screen-pinning** plus launcher-style
behavior:

- App set as **home/launcher** (or pinned) so wake → app foreground.
- **Keep-screen-on** while interacting; immersive full-screen.
- No requirement to be device owner for MVP, but document the **Device Owner / Lock Task**
  upgrade path for a stronger kiosk later.
- **[ASSUMPTION]** Single local user; no multi-account.

### 5.3 Screens

1. **Home / Capture** — dominant press-and-hold record button (≥ 60% of screen), state
   ring (idle/recording/transcribing), small status line (connectivity, last sync). On
   morning first-wake, the **Daily Summary** card auto-appears here.
2. **Transcript review** — editable text field prefilled with STT output; **5-second
   countdown ring**; buttons **Send / Edit / Cancel**. Editing cancels the countdown.
3. **Proposal review** — list of proposed actions, each with a plain-language explanation,
   per-action Approve/Reject, and a "sensitive" badge where a PIN will be required.
4. **Session PIN** — appears when a sensitive action is approved and the session is not yet
   unlocked; unlocks for a configurable session window.
5. **Daily summary** — calendar + tasks + overdue + reminders; "Speak again" button; task
   completion prompts ("Did you finish X?").
6. **History (light)** — recent captures and their outcomes (read from server).
7. **Settings (dev)** — backend URL, device pairing, transcription location toggle,
   accessibility (hold vs tap-toggle), test/mock mode.

### 5.4 Recording & feedback

- **Format:** 16 kHz mono WAV/PCM [DECISION] (Vosk-friendly, small).
- **Feedback:** start = short beep + short vibrate; stop = distinct beep + vibrate;
  send/cancel = subtle haptic. (Honors system silent mode.)
- **Audio cache:** raw audio saved **temporarily** on device (app-private storage) until
  the backend confirms receipt, then deleted locally per retention setting
  (**[ASSUMPTION]** delete on confirmed upload; keep ≤ 24 h fallback if offline).

### 5.5 Speech-to-text on device

- **Vosk** small English model bundled or first-run downloaded to app storage.
- Transcription runs **on release** of the button; show "transcribing…" state.
- **Server-side fallback (designed, optional for MVP):** a flag lets the app upload audio
  and request server transcription if on-device quality/perf is poor. Backend exposes a
  transcription endpoint that uses a server STT engine (e.g. whisper.cpp/faster-whisper)
  behind the same adapter interface. **[ASSUMPTION]** MVP ships on-device only; server STT
  is a config-flag-gated enhancement.

### 5.6 Auth & secure storage

- **Device token** stored in **Android Keystore-backed EncryptedSharedPreferences**.
- Token sent as `Authorization: Bearer <device-token>`.
- **Session PIN** verified server-side (or via a server-issued session grant); the phone
  holds only a short-lived **session token** after PIN success, never the PIN itself.

### 5.7 Networking

- **Retrofit + OkHttp + kotlinx.serialization** [DECISION]; coroutines for async.
- Offline queue: captures recorded offline are queued and uploaded when connectivity
  returns (idempotency keys prevent duplicates).
- Configurable base URL (no hardcoded IPs in source; injected via build config / settings).

### 5.8 Android dependency management

- **Gradle Version Catalog** (`libs.versions.toml`) for centralized, pinned versions.
- **Gradle wrapper** committed (pinned Gradle version) for reproducible builds.
- R8/ProGuard for release; no secrets in the APK (backend URL is config, device token is
  runtime-provisioned).

---

## 6. Backend Design

### 6.1 Service shape

A single **FastAPI** application plus one or more **worker** processes, sharing the same
codebase and DB models. Clear module separation:

```
api/            FastAPI routers, request/response schemas, auth deps
core/           config, logging, security, idempotency, errors
domain/         business logic: tasks, notes, approvals, reminders
integrations/   interfaces + adapters (llm, gmail, calendar, github, claudecode, stt)
                each with a real adapter + a mock adapter
workers/        queued jobs: interpret, execute-action, reminders, escalation, cc-jobs
db/             SQLAlchemy models, Alembic migrations, session management
schemas/        shared Pydantic schemas (also the LLM action contract)
media/          media-store abstraction (filesystem; pluggable to S3-compatible later)
```

### 6.2 API endpoints (MVP)

All endpoints: **device-token auth**, **Pydantic-validated** input, structured errors,
idempotency where they create resources.

| Method | Path | Purpose | Auth | Sensitive |
|---|---|---|---|---|
| POST | `/v1/devices/register` | Exchange registration code → device token | pairing code | — |
| POST | `/v1/devices/session/pin` | Verify session PIN → short-lived session token | device token | — |
| POST | `/v1/captures` | Upload audio + transcript + metadata (idempotent) | device | — |
| PATCH | `/v1/captures/{id}/transcript` | Submit/edit transcript before interpret | device | — |
| POST | `/v1/captures/{id}/interpret` | Trigger interpretation (or auto on upload) | device | — |
| GET | `/v1/captures/{id}/proposals` | Get proposed actions | device | — |
| POST | `/v1/proposals/{id}/approve` | Approve an action (idempotent) | device | maybe* |
| POST | `/v1/proposals/{id}/reject` | Reject an action | device | — |
| GET | `/v1/tasks` | List tasks (filter by status/priority) | device | — |
| POST | `/v1/tasks` | Create task | device | — |
| PATCH | `/v1/tasks/{id}` | Update task (status, snooze, done) | device | — |
| POST | `/v1/tasks/{id}/snooze` | Snooze task/reminder | device | — |
| POST | `/v1/tasks/{id}/done` | Mark done (explicit only) | device | — |
| GET | `/v1/summary/daily` | Daily summary payload | device | — |
| GET | `/v1/audit` | Audit log (paginated, filtered) | device | — |
| GET | `/v1/healthz` | Liveness/readiness | none | — |

\* An approve call becomes sensitive (requires a valid session token from PIN) when the
underlying action's `sensitivity` is `pin_required` (e.g. invoke Claude Code, draft email
to a contact, broad email search).

### 6.3 Idempotency

- Client generates an **`Idempotency-Key`** (UUID) per capture and per
  approve/create call.
- Backend stores `(key, endpoint, request-hash) → response` and returns the prior result on
  replay. Prevents duplicate tasks, issues, calendar proposals, email searches.
- External-action executors also use **deterministic external idempotency** where the
  provider supports it (e.g. GitHub issue title+body hash check before create).

### 6.4 Error handling & retries

- Uniform error envelope: `{ "error": { "code", "message", "request_id" } }`.
- **Retries with exponential backoff + jitter** for transient integration failures
  (network, 429, 5xx); **no retry** on validation/4xx.
- **Circuit-breaker / dead-letter**: jobs that exhaust retries move to a dead-letter state
  and surface in the audit log + an admin view; never silently dropped.

### 6.5 Configuration strategy

- **Pydantic Settings** loads from environment (`.env` locally, real env on `@mini`).
- Distinct config sets for **dev / staging / prod** via `APP_ENV`.
- No secrets in code or committed config. See §15.

### 6.6 Logging

- **Structured JSON logs** (e.g. `structlog`) with `request_id`, `device_id`, `action_id`.
- **Redaction by construction:** transcript text, email bodies, and LLM raw I/O are
  **never** logged at info level. Sensitive payloads are stored in the DB/media store and
  referenced by ID in logs. A redaction filter strips known sensitive keys defensively.

---

## 7. Database Schema Proposal

PostgreSQL. Operational data only; **no raw audio bytes** in the DB (see §8). All tables
have `id` (UUID), `created_at`, `updated_at` unless noted. Enums implemented as Postgres
enums or check-constrained text.

### 7.1 Core tables

**`devices`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| name | text | friendly name ("Robin") |
| token_hash | text | hash of long-lived device token (never store raw) |
| status | enum(`active`,`revoked`) | |
| last_seen_at | timestamptz | |

**`sessions`** (PIN-unlocked windows)
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| device_id | uuid fk | |
| token_hash | text | short-lived session token hash |
| expires_at | timestamptz | session window |
| pin_verified_at | timestamptz | |

**`captures`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| device_id | uuid fk | |
| media_id | uuid fk → media_objects | nullable until uploaded |
| transcript_raw | text | STT output (sensitive) |
| transcript_edited | text | user-edited final (sensitive) |
| transcription_source | enum(`device`,`server`) | |
| status | enum(`received`,`interpreting`,`proposed`,`executed`,`cancelled`,`error`) | |
| idempotency_key | text unique | |
| captured_at | timestamptz | |

**`interpretations`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| capture_id | uuid fk | |
| provider | text | `claude`/`openai`/`mock` |
| model | text | |
| intent | text | e.g. `daily_summary`, `email_followup`, `code_task`, `note` |
| raw_response_id | uuid fk → media/audit blob | raw LLM I/O stored out of normal logs |
| validation_status | enum(`valid`,`invalid`,`repaired`) | schema validation result |

**`proposed_actions`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| interpretation_id | uuid fk | |
| type | enum(`create_task`,`create_note`,`propose_event`,`email_search`,`email_draft`,`create_github_issue`,`prepare_cc_job`,`invoke_cc_job`,`update_task`) | |
| payload | jsonb | validated action params |
| explanation | text | human-readable "what I will do" |
| sensitivity | enum(`normal`,`approval`,`pin_required`) | |
| status | enum(`pending`,`approved`,`rejected`,`executing`,`executed`,`failed`) | |
| idempotency_key | text | |
| external_ref | jsonb | e.g. issue URL, ICS path, draft id |

**`tasks`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| title | text not null | |
| notes | text | |
| status | enum(`active`,`scheduled`,`snoozed`,`done`,`archived`) | |
| priority | enum(`low`,`normal`,`high`,`urgent`) | default `normal` |
| due_at | timestamptz | |
| scheduled_start | timestamptz | time block start |
| scheduled_end | timestamptz | time block end (marked busy) |
| tags | text[] | |
| source_capture_id | uuid fk | |
| source_media_id | uuid fk | |
| snooze_until | timestamptz | |
| recurrence | jsonb | bounded rule (count/until) — see §19 |
| last_nag_at | timestamptz | for nag throttling |
| completed_at | timestamptz | set only on explicit done |

**`notes`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| body | text | |
| source_capture_id | uuid fk | |
| linked_task_id | uuid fk | nullable |
| tags | text[] | |

**`reminders`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| task_id | uuid fk | |
| fire_at | timestamptz | |
| cadence | enum(`once`,`hourly`,`daily`) | nag cadence |
| active | bool | |

**`calendar_proposals`**
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| task_id | uuid fk | nullable |
| title | text | |
| start_at / end_at | timestamptz | |
| busy | bool | time blocks marked busy |
| ics_media_id | uuid fk → media_objects | generated .ics stored in media store |
| status | enum(`proposed`,`approved`,`rejected`,`exported`) | |
| metadata | jsonb | venue, ticket ref, source email link, etc. |

**`integration_accounts`** (OAuth tokens for Gmail/Calendar/GitHub — stored encrypted)
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| provider | enum(`gmail`,`google_calendar`,`github`) | |
| scopes | text[] | least-privilege scopes granted |
| token_ref | text | reference to encrypted secret (not the token itself) |
| status | enum(`active`,`revoked`,`expired`) | |

**`media_objects`** (metadata only; bytes on disk — see §8)
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| kind | enum(`audio`,`ics`,`attachment`,`llm_blob`,`export`) | |
| path | text | relative path under media root |
| size_bytes | bigint | |
| sha256 | text | integrity/idempotency |
| retention_class | enum(`audio`,`derived`,`pinned`) | drives lifecycle |
| expires_at | timestamptz | nullable |

**`audit_log`** (append-only — see §18)
| col | type | notes |
|---|---|---|
| id | uuid pk | |
| ts | timestamptz | |
| actor | enum(`device`,`worker`,`llm`,`system`,`user`) | |
| event | text | e.g. `CAPTURE_RECEIVED`, `INTERPRETATION_CREATED`, `ACTION_APPROVED`, `TOOL_CALL`, `ACTION_EXECUTED`, `ACTION_FAILED`, `PIN_VERIFIED` |
| capture_id / action_id / task_id | uuid | nullable refs |
| summary | text | redacted, no raw sensitive content |
| detail_ref | uuid fk → media_objects(llm_blob) | optional pointer to full detail |

### 7.2 Indices & constraints (highlights)

- `captures.idempotency_key` unique; `tasks(status, due_at)`, `tasks(priority, status)`,
  `reminders(active, fire_at)` for the worker scans; `audit_log(ts)` for queries.
- FKs `ON DELETE RESTRICT` for audit-referenced rows (preserve audit integrity).

---

## 8. Media/Audio Storage Design

### 8.1 Principles

- Raw audio and other binaries are **stored on the filesystem**, not in Postgres, so the
  operational DB stays small/fast. DB holds only `media_objects` metadata.
- Root: a Docker volume mounted at e.g. `/data/media` on `@mini` (host path configurable
  via env; **never** committed). Layout:
  ```
  /data/media/
    audio/<yyyy>/<mm>/<dd>/<capture_id>.wav
    ics/<proposal_id>.ics
    attachments/<sha256>.<ext>
    llm/<interpretation_id>.json        # raw LLM I/O (sensitive, out of logs)
    exports/<...>                        # audit exports, generated reports
  ```

### 8.2 50 GB cap & lifecycle

- **Configurable cap `MEDIA_MAX_BYTES` (default 50 GB).** A worker enforces it:
  - Tracks total usage from `media_objects.size_bytes` (verified periodically against disk).
  - **Retention classes:** `audio` (shortest), `derived` (ICS/exports), `pinned` (never
    auto-deleted).
  - **[ASSUMPTION]** Default audio retention: **30 days**, then eligible for pruning;
    pruning prioritizes oldest `audio` first, then `derived`, never `pinned`.
  - When usage exceeds a high-water mark (e.g. 90% of cap), prune oldest eligible objects
    until below a low-water mark (e.g. 75%). All prunes are audited.
- **Integrity:** `sha256` recorded; used for dedup (attachments) and tamper detection.
- **Encryption-at-rest:** **[ASSUMPTION]** rely on host disk encryption (BitLocker/LUKS) for
  MVP; per-object encryption is a future enhancement (§22).

### 8.3 Access

- Media is served only through the authenticated API (no static public serving), with
  authorization checks tying media to the requesting device.

---

## 9. LLM / Tool-Calling Design

### 9.1 Provider abstraction

**[DECISION]** Define an `LLMProvider` interface; ship a **Claude adapter** first, an
**OpenAI adapter** later, and a **mock adapter** for dev/tests.

```python
class LLMProvider(Protocol):
    def interpret(self, request: InterpretRequest) -> InterpretResult: ...
```

- Model IDs and provider are config-driven (`LLM_PROVIDER=claude`, `LLM_MODEL=...`).
- **Claude-first** per the brief. The latest, most capable Claude model is selected via
  config; the design does not hardcode a model so it can track new releases.
  *(When implementation begins, consult current model IDs/pricing via the project's
  `claude-api` reference rather than assuming from memory.)*

### 9.2 Structured action contract

- The LLM is instructed (system prompt + **tool/function schema**) to return a list of
  **proposed actions** matching a strict JSON schema (mirrored by Pydantic models in
  `schemas/`). This is the single contract shared between LLM, backend, and (loosely) the
  app's proposal UI.
- **The LLM never executes anything.** It only proposes. The backend:
  1. Parses + **validates** against the schema (reject/repair on mismatch — bounded repair
     attempts, then fail safe).
  2. Assigns `sensitivity` per action type (server-side policy, not LLM-controlled).
  3. Persists proposals for human approval.

Action types (MVP): `create_task`, `create_note`, `update_task`, `propose_event`,
`email_search`, `email_draft`, `create_github_issue`, `prepare_cc_job`, `invoke_cc_job`,
`daily_summary` (read-only assembly), `clarify` (ask the user a question with options).

### 9.3 Context discipline (privacy)

- The interpreter includes **task/note context** by default.
- It includes **email/calendar data only** when the intent clearly requires it or the user
  explicitly asks (§ brief). The backend gates which context is fetched **before** calling
  the LLM, so the model never sees email/calendar unless warranted.
- Raw LLM input/output stored in the media store (`llm/`) and referenced from audit — not
  emitted in logs.

### 9.4 Approval coupling

- **During development: every LLM-produced action requires approval.** The assistant
  explains each action in plain language before execution.
- Sensitivity policy decides whether approval also needs a **session PIN** (§13).

### 9.5 Clarification flow

- When the target is ambiguous (e.g. which repo), the LLM emits a `clarify` action with
  options; the phone presents choices; the answer feeds a follow-up interpretation. No
  guessing on ambiguous, side-effecting targets.

---

## 10. Gmail Integration Design

### 10.1 Scope & permissions (least privilege)

- **[DECISION]** Use **read-only** Gmail scope (`gmail.readonly`) for searching/summarizing
  and **`gmail.compose`** (draft-only) for drafting. **No send scope** is requested at all
  in MVP — the system *cannot* send mail even if asked.
- This system designs **its own permission model** independent of any existing Claude↔Gmail
  connection (per the brief): its own OAuth client, its own least-privilege scopes, its own
  encrypted token storage, its own audit trail.

### 10.2 Behavior

- **Default window:** last 1 day [ASSUMPTION] (the brief says "last few days"; MVP defaults
  conservatively to 1 day and allows override by explicit command). Never searches all mail
  without explicit instruction + session PIN.
- **Summarize-before-act:** candidate results are summarized (sender/subject/gist) and shown
  before any deeper step.
- **Attachments:** may open an attachment **only** when it clearly matches the request;
  uncertain attachments require approval + PIN. Opened attachments are stored as
  `media_objects(kind=attachment)`.
- **Drafting:** allowed (draft only); a draft to a person is **sensitive** → approval + PIN.

### 10.3 Safety

- Every Gmail tool call is audited (query terms summarized, not full bodies).
- Email bodies are never logged; if needed for interpretation they're passed to the LLM and
  stored as an `llm_blob`, referenced by ID.

---

## 11. Calendar / ICS Integration Design

### 11.1 MVP: ICS generation + proposals

- MVP **does not** write directly to calendars. It **generates `.ics` files / proposed
  events** (`calendar_proposals` + an `ics` media object).
- The user reviews/approves; the ICS can be opened/imported into Google/Outlook/Apple
  Calendar. This neatly supports the user's three calendar ecosystems without per-provider
  write integrations on day one.
- All calendar actions **require approval during development**.

### 11.2 Availability & time-blocking

- **Default work hours 9 AM–5 PM** [given]. "Carve out time" looks at **actual calendar
  availability**.
- **[DECISION — resolved]** Availability is read from a **single aggregate calendar** that
  the user already keeps synced with their Google/Outlook/Apple calendars, via that
  calendar's **private ICS feed URL** (the "secret address in iCal format" both Google and
  Outlook expose). The backend fetches that one URL read-only and computes free/busy from
  it. This means **no per-provider OAuth client and no calendar write scopes** — the
  provider apps already handle their own sync/auth, and the assistant only ever sees the one
  feed. The feed URL is a **secret**, stored in `.env` (`CALENDAR_ICS_FEED_URL=...`), never
  committed.
- The feed is fetched on a short cache (e.g. 5–15 min) to avoid hammering it. If
  `CALENDAR_ICS_FEED_URL` is unset, the assistant falls back to "assume 9–5 free unless a
  task time-block exists" and **says so** in its proposal.
- Time blocks created for tasks are marked **busy**.

### 11.3 Event metadata (ticket/event emails)

- For event/ticket emails, capture whatever is available: title, venue, date/time, ticket
  PDF/attachment, QR/barcode if accessible, link to the original email, and other useful
  metadata — stored in `calendar_proposals.metadata` + attachment media objects.

### 11.4 Future: direct calendar writes

- Later versions add direct event creation via Google Calendar API (write scope), then
  Microsoft Graph (Outlook) and CalDAV (Apple), behind the same `CalendarProvider`
  interface. Writes always gated by approval.

---

## 12. GitHub / Claude Code Automation Design

### 12.1 GitHub

- **[DECISION]** Use a **fine-grained GitHub PAT** (or GitHub App later) scoped to **only
  the specific repos** the assistant manages, with **Issues: read/write** and
  **Contents/Pull requests** as needed for Claude Code branches. No org-wide or `repo`
  blanket scope.
- Creating an issue: backend checks for an existing open issue with the same title hash
  (idempotency) before creating; the issue body is shown to the user (draft) before
  creation.

### 12.2 Claude Code job pipeline

The flagship sensitive flow. Stages:

```
1. prepare_cc_job  (proposal, NOT sensitive to prepare):
     - resolve/confirm target repo (clarify if ambiguous)
     - assemble a Claude Code job prompt (shown to user)
     - create local task + (approved) GitHub issue
2. approval of the bundle (issue + task + prepared job)
3. invoke_cc_job (sensitive: approval + SESSION PIN required):
     - enqueue a Claude Code job in a sandboxed worker on @mini
     - worker checks out the repo into an ISOLATED workspace/worktree
     - runs Claude Code against the prepared prompt
     - produces a BRANCH + PR/diff — NEVER auto-merges, NEVER pushes to default
4. result surfaced to phone: PR link, summary of changes, audit entry
```

- **Sandboxing:** Claude Code jobs run in a constrained worker container with access only to
  the target repo workspace and the minimum credentials (the scoped GitHub token), separate
  from the API container.
- **No auto-merge / no force-push / no default-branch writes.** Human merges via GitHub.
- Every stage audited; the invoke stage records `PIN_VERIFIED` + `CC_JOB_INVOKED` +
  outcome.

### 12.3 Routing notes/coding commands

- For coding-related input, the LLM may propose local task, GitHub issue, and/or a Claude
  Code job and picks the most appropriate; ambiguity → `clarify` with options.

---

## 13. Security and Approval Model

### 13.1 Authentication layers

1. **Device token** (long-lived, hashed at rest) — identifies the phone for all calls.
2. **Session token** (short-lived) — issued after **PIN/pattern** verification; required
   for `pin_required` actions. **[ASSUMPTION]** session window default **15 minutes**,
   configurable; one PIN unlocks sensitive actions for that window (not every action).

### 13.2 Sensitivity tiers

| Tier | Examples | Gate |
|---|---|---|
| `normal` | create task/note, propose event, daily summary, mark task done | approval (dev); auto-approvable later |
| `approval` | create GitHub issue, generate ICS, limited email search | explicit approval |
| `pin_required` | invoke Claude Code, draft/contact a person, broad email search, open uncertain attachment, any code-affecting automation | approval **+ session PIN** |

### 13.3 Approval policy

- **Development:** **all** actions require explicit approval (per brief).
- **Later (post-hardening), auto-approve candidates:** show my day, check task completion,
  suggest what to do today, limited email window checks for specific follow-ups. These are
  read-only or low-risk. Everything in `pin_required` always stays gated.

### 13.4 Defense in depth

- LLM output is **never trusted**: schema validation, server-assigned sensitivity, and the
  fact that the LLM cannot execute anything.
- Least-privilege scopes for every integration; tokens encrypted at rest, referenced by ID.
- Backend not exposed to the public internet (Tailscale/Cloudflare Tunnel); HTTPS always.
- Rate limiting on auth + capture endpoints; lockout/backoff on repeated PIN failures.
- Input validation on every endpoint; size limits on uploads; content-type checks on media.

---

## 14. Public GitHub Repository Safety Model

The repo is designed to be **public from day one**.

- **Nothing secret is ever committed:** API keys, OAuth tokens/clients, device tokens, DB
  passwords, SSH details, private hostnames/tunnels, internal IPs (when sensitive), media,
  transcripts, audio, generated ICS, logs, audit exports.
- **Only `*.example` config is committed** (e.g. `.env.example`) with placeholder values.
- **`.gitignore`** (comprehensive — see below) excludes Android build outputs, backend
  artifacts, Docker local volumes, local DBs, IDE files, logs, all media/audio/transcripts,
  generated credentials/keystores, and `.env*` (except `*.example`).
- **Secret scanning** runs in CI (Gitleaks) **and** as a local pre-commit hook, so secrets
  are caught before they ever reach a push.
- **No machine-specific absolute paths** in committed code/config; everything is env-driven
  (the host media path, the mini's address, the LAN IP — all come from `.env` or runtime
  config). Docs use placeholders like `<mini-host>` and `rs@nucboxk8plus` only as
  illustrative examples, not baked into code.
- **Branch protection** on `main` (require PR + green CI + secret scan) once collaborators
  exist.

### 14.1 `.gitignore` coverage (representative)

```
# Secrets / env
.env
.env.*
!.env.example
*.pem
*.key
*.keystore
*.jks
secrets/
credentials/
*token*.json
service-account*.json

# Media / sensitive runtime data (NEVER commit)
data/
media/
audio/
transcripts/
*.wav
*.mp3
*.m4a
*.ics            # except sanitized fixtures under tests/fixtures/
exports/
*.log
logs/

# Backend
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Android
*.apk
*.aab
/android/build/
/android/app/build/
/android/.gradle/
local.properties

# Docker / local DB
docker-compose.override.yml
pgdata/
*.sqlite
*.db

# IDE / OS
.idea/
.vscode/
*.iml
.DS_Store
```

(ICS/log/audit exports stay out of git unless they are explicitly sanitized fixtures placed
under `tests/fixtures/`.)

### 14.2 If a secret is accidentally committed (rotation runbook)

1. **Rotate immediately** at the provider (revoke the key/token; issue a new one). The leaked
   value is compromised the moment it's pushed — rotation is mandatory, not optional.
2. Remove from history (`git filter-repo` / BFG) and force-push **after** rotation.
3. Invalidate any derived sessions/device tokens if applicable.
4. Audit access logs at the provider for misuse.
5. Add/extend a Gitleaks rule to catch that pattern in future. Document the incident.

---

## 15. Secret-Management Strategy

- **Source of truth at runtime:** environment variables, loaded from `.env` locally and from
  the deployment environment on `@mini`. **[ASSUMPTION]** MVP uses `.env` files on `@mini`
  (outside git, restricted file perms). Future: a secrets manager (Doppler/Vault/SOPS) —
  see §22.
- **Committed:** `.env.example` per service with **placeholders only**:
  ```
  APP_ENV=dev
  DATABASE_URL=postgresql://user:CHANGE_ME@db:5432/pocket
  REDIS_URL=redis://redis:6379/0
  MEDIA_ROOT=/data/media
  MEDIA_MAX_BYTES=53687091200      # 50 GB
  LLM_PROVIDER=mock                # claude | openai | mock
  LLM_API_KEY=CHANGE_ME
  GMAIL_OAUTH_CLIENT_ID=CHANGE_ME
  CALENDAR_ICS_FEED_URL=CHANGE_ME   # private iCal feed of the aggregate calendar
  GITHUB_TOKEN=CHANGE_ME
  GITHUB_REPO_ALLOWLIST=OWNER/repo-a,OWNER/repo-b   # repos the assistant may touch
  DEVICE_TOKEN_PEPPER=CHANGE_ME
  ```
- **Environment separation:** `APP_ENV` selects dev/staging/prod config; secrets differ per
  environment and never cross over.
- **At rest:** integration OAuth tokens and device-token peppers are encrypted (app-level
  encryption keyed by a master key from env) and stored as references; raw values never in
  DB columns logged or returned by the API.
- **Access discipline:** Claude Code (the assistant) must ask before creating any real
  credential or OAuth client; MVP development uses **mock** providers by default.

---

## 16. Dependency / Vulnerability-Management Strategy

**Backend (Python):**
- **Pin & lock** dependencies (e.g. **Poetry** or **uv** with a committed lockfile, or
  `pip-tools` `requirements.txt` + `requirements.lock`). [DECISION] uv + lockfile for speed
  and reproducibility.
- **`pip-audit`** (or `safety`) in CI for known CVEs.
- **Ruff** (lint) + **mypy** (types) + **Bandit** (Python security linter) in CI.

**Android (Kotlin/Gradle):**
- **Version Catalog** (`libs.versions.toml`) + committed Gradle wrapper for pinned,
  centralized versions.
- **OWASP Dependency-Check** or **Gradle `dependencyUpdates`** for vulnerable/outdated libs.

**Containers:**
- Pin base images by **digest**; use **slim/distroless** where possible; run as **non-root**;
  scan images with **Trivy** in CI.

**Automation:**
- **Dependabot** (or **Renovate**) enabled for `pip`/`gradle`/`docker`/`github-actions`
  ecosystems, grouped, with auto-PRs gated by CI.

---

## 17. CI / Security-Check Strategy

**GitHub Actions** workflows (run on PR + push):

1. **`backend-ci`**: install (locked deps) → Ruff → mypy → Bandit → pytest (unit +
   contract, mocked integrations) → pip-audit.
2. **`android-ci`**: Gradle assembleDebug → ktlint/detekt → unit tests → dependency check.
   (No signing secrets in CI; debug builds only.)
3. **`security`**: **Gitleaks** secret scan (full history on schedule, diff on PR) →
   **Trivy** image scan → CodeQL (optional) for Python/Kotlin.
4. **`docker-build`**: build images with pinned digests; fail on Trivy HIGH/CRITICAL.

- **Pre-commit** (local, `@dev-pc`): Gitleaks, Ruff, end-of-file/whitespace, large-file
  guard, `.env` guard. Mirrors CI so problems are caught before push.
- **Branch protection:** require green CI + secret scan before merge to `main`.

---

## 18. Audit Logging Model

- **Append-only `audit_log`** table (see §7). Every sensitive/state-changing step writes an
  event: capture received, interpretation created (+ provider/model), each tool call,
  approval/rejection, PIN verification, action executed/failed, media prune, token
  registration/revocation, Claude Code job invoked + outcome.
- **Redacted summaries only** in the audit row (`summary`); full detail (raw LLM I/O, full
  query) lives in the media store as an `llm_blob`/detail object and is referenced by
  `detail_ref` — keeping sensitive content out of queryable text and out of logs.
- **Tamper-evidence (future):** hash-chain each audit row (`prev_hash`) for an append-only
  guarantee (§22). MVP keeps it append-only by convention + DB constraints.
- **Exports:** audit can be exported (e.g. for review); exports are written to
  `media/exports/` and are **git-ignored** (never committed unless a sanitized fixture).
- `GET /v1/audit` exposes a paginated, filtered, **redacted** view to the phone.

---

## 19. Task / Reminder Behavior

- **Fields & statuses & priorities:** exactly as specified in the brief (see `tasks` table,
  §7). Statuses: `active`, `scheduled`, `snoozed`, `done`, `archived`. Priorities: `low`,
  `normal`, `high`, `urgent`.
- **Defaults:** new vague task → **normal** priority.
- **Overdue escalation:** a worker scans tasks; an **overdue** task is auto-raised to
  **high**. (Urgent stays urgent.)
- **Nagging:**
  - **urgent** → may nag **hourly**.
  - **high + overdue** → may nag **daily**.
  - Nag throttled via `last_nag_at`; **snooze** suppresses nags until `snooze_until`.
- **Snooze:** user can snooze any reminder/task; sets `status=snoozed` + `snooze_until`;
  reactivates after the window. Snoozing is always available so reminders never become
  overwhelming.
- **Recurrence (bounded):** recurring reminders **must** be bounded (`count` or `until`) or
  trivially clearable, so they can't fill the calendar forever. A "clear all recurrences for
  this task" action is provided.
- **Completion is explicit:** tasks are **only** marked done when the user manually marks
  done or explicitly states they completed it. The assistant may **ask** ("Did you finish
  X?") for high-priority/overdue tasks but never auto-completes.

---

## 20. Daily Summary Behavior

- **Command:** "What's my day look like?" → `GET /v1/summary/daily`.
- **Contents:** calendar events, active/scheduled tasks, **overdue-not-done** tasks,
  reminders, and **important email follow-ups only if relevant** (and only with the email
  read policy of §10).
- **Output:** both **displayed** (cards) and **spoken** (on-device TTS).
- **Proactive morning behavior:** on the **first screen-wake of the day**, the app
  auto-requests and shows the daily summary (and can speak it). **[ASSUMPTION]** "morning"
  = first wake after a configurable start hour (default 5 AM) to avoid speaking at 2 AM.
- **Interactive:** prompts "Did you finish <overdue/high-priority task>?" and supports
  **snoozing** directly from the summary.
- This flow is **read-only** → a prime candidate for auto-approval after the development
  approval phase.

---

## 21. MVP Scope

**In scope:**
- Kiosk Android app: wake → **press-and-hold** record (sound+vibration) → **Vosk on-device
  transcription** → editable transcript with **5-second auto-send countdown** →
  **Send/Edit/Cancel** → temporary local audio cache.
- Device registration + **device token**; **session PIN** for sensitive actions.
- FastAPI backend on `@mini` via **Docker Compose** (API + worker + Postgres + Redis +
  media volume + reverse proxy).
- Endpoints: device register/auth, session PIN, upload capture, submit/edit transcript,
  interpret, get proposals, approve/reject, list/create/update tasks, snooze, mark done,
  daily summary, audit.
- **LLM interpretation (Claude-first, mock by default in dev)** → validated structured
  proposals → **all require approval**.
- **Internal task system** with priority escalation + bounded reminders + snooze.
- **Three flagship commands:** "What's my day look like?", "Did anyone get back to me?"
  (1-day read-only email), and the **day-trader GitHub issue + Claude Code** flow
  (approval + PIN gated).
- **Calendar via ICS proposals**; default 9–5 work hours; time-blocks marked busy.
- **Gmail read-only + draft-only** (no send) with summarize-before-act + default 1-day
  window.
- **GitHub issue creation** (scoped token) + **Claude Code job** pipeline (sandboxed,
  branch/PR only, no auto-merge).
- **Full audit logging**; **structured redacted logs**; **media store with 50 GB cap +
  lifecycle**.
- **Public-repo safety**: `.gitignore`, `.env.example`, Gitleaks (pre-commit + CI),
  Dependabot, CI (lint/type/test/security), pinned/locked deps.

**Explicitly out of MVP:** real lock-screen overlay / power-button activation; direct
calendar writes; email sending; server-side STT as default; multi-user; per-object media
encryption; non-English STT.

---

## 22. Non-MVP Future Features

- **True kiosk activation:** Device Owner + Lock Task, lock-screen overlay, power-button or
  hardware-key / "Siri-like" wake-word activation.
- **Server-side STT** (whisper.cpp/faster-whisper) as default or quality fallback.
- **Direct calendar writes** (Google → Outlook/Graph → Apple/CalDAV) behind
  `CalendarProvider`.
- **Vikunja integration** as an optional external task backend (interface already isolates
  task storage).
- **Email send** (with strong gating) if ever desired; currently intentionally disabled.
- **Secrets manager** (Vault/Doppler/SOPS) replacing `.env` on `@mini`.
- **Per-object media encryption** + audit **hash-chaining** for tamper-evidence.
- **Auto-approval** of read-only/low-risk actions after a hardening period.
- **Multi-provider LLM** (OpenAI adapter) + on-device small-model fallback for offline
  interpretation of simple commands.
- **Push notifications** to the phone for reminders/nags (currently pull/on-wake).
- **Multi-device / multi-user**, richer notes/projects, full-text search over notes/tasks.

---

## 23. Open Questions

Each has a proposed default ([ASSUMPTION]) so work can proceed without blocking.

1. **Remote access method** — Tailscale vs Cloudflare Tunnel vs LAN-only? *Default:
   Tailscale* (private, no public exposure). **Needs your confirmation** before any
   network exposure is set up.
   I can set up tailscale as well as cloudflare. If both are useful for different reasons, I'll set up both.
2. **Email default window** — brief says "last few days"; *default: 1 day*, overridable by
   command. Confirm preferred default.
   confirmed.
3. **Calendar availability source for "carve out time"** — read Google Calendar
   (`calendar.readonly`) vs ICS-only? *Default: Google read-only; fall back to 9–5
   assumption and say so.* Confirm whether to set up a Google OAuth client (a credential
   step that needs approval).
   I'd like to give access to a calendar that is already synced with my other calendars. that way it accesses only that calendar and the windows calendar/apple calendar will handle the oauth stuff
4. **Audio retention** — *default 30 days* then prune under the 50 GB cap. Confirm.
confirm
5. **Session PIN window** — *default 15 min*. Confirm; also choose PIN vs pattern.
confirmed and pin. 
6. **Which repos** the assistant may touch for GitHub/Claude Code (the "day trader site"
   repo identity). Needs an explicit allowlist before any GitHub/CC integration is wired.
   create an allow list and we can add to it
7. **Morning summary start hour** — *default 5 AM*. Confirm.
confirm
8. **TTS engine** — on-device Android TTS (default) vs a higher-quality engine later.
not sure what this means
9. **Dependency tooling** — uv (recommended) vs Poetry for the backend. Confirm preference.
not sure what this means
10. **Does the existing Claude↔Gmail connection** need to be reused, or do we provision a
    fresh, independent least-privilege OAuth client (recommended)? *Default: fresh, own
    client.*
    not sure. I know claude on this mac has access to my email. not sure past that.

---

## 24. Recommended Implementation Phases

> No phase below is executed as part of this design doc. Each external/credential/remote
> step will be explained and approved before it runs.

**Phase 0 — Repo & safety scaffolding (no secrets, no services):**
- Monorepo skeleton, `.gitignore`, `.env.example` files, pre-commit (Gitleaks/Ruff),
  GitHub Actions CI (lint/type/test/security), Dependabot config, README + this DESIGN.md.

**Phase 1 — Backend core with mocks (local Docker):**
- FastAPI app, Postgres + Alembic, Redis, models/migrations, capture/transcript/task
  endpoints, **mock** LLM/Gmail/Calendar/GitHub/CC adapters, structured logging, audit log,
  idempotency, tests. Runs locally (Mode B) and on `@mini` (Mode A) — both with mocks.

**Phase 2 — Android capture client:**
- Compose kiosk UI, press-and-hold record + feedback, **Vosk** STT, editable transcript +
  5-sec countdown, device registration, device-token auth, upload to backend, proposal
  review + approve/reject, session PIN, daily-summary display + TTS. Built/installed via ADB
  on `@dev-pc`.

**Phase 3 — Task system + daily summary + reminders:**
- Full task lifecycle, escalation/nag/snooze worker, bounded recurrence, daily summary
  assembly, proactive morning summary.

**Phase 4 — Real LLM (Claude) interpretation:**
- Wire the Claude adapter behind the abstraction (config-flagged), structured-action
  schema + validation/repair, clarify flow. Still **all actions require approval**.

**Phase 5 — Integrations (least privilege, gated):**
- Gmail read-only + draft-only (command 2), ICS calendar proposals + availability, GitHub
  issue creation. Each behind approval (and PIN where sensitive). Credentials provisioned
  only with explicit approval.

**Phase 6 — Claude Code automation (most sensitive):**
- Sandboxed CC job worker, prepare→approve→(PIN)→invoke pipeline, branch/PR output, the
  day-trader flagship flow end-to-end. No auto-merge.

**Phase 7 — Remote access + hardening:**
- Tailscale/Cloudflare tunnel, HTTPS, rate limiting, media lifecycle enforcement, audit
  export, selective auto-approval of read-only actions, docs polish.

---

## 25. Initial Repo Structure

```
pocket-assistant/
├── README.md
├── DESIGN.md                       # this document
├── LICENSE
├── .gitignore
├── .gitleaks.toml
├── .pre-commit-config.yaml
├── .github/
│   ├── workflows/
│   │   ├── backend-ci.yml
│   │   ├── android-ci.yml
│   │   ├── security.yml
│   │   └── docker-build.yml
│   └── dependabot.yml
│
├── docs/
│   ├── architecture.md
│   ├── dev-local.md                # local dev loop (@dev-pc, mocks)
│   ├── deploy-mini.md              # remote deploy to @mini via ssh rs@nucboxk8plus
│   ├── android-testing.md          # ADB on @dev-pc, build/install/logcat
│   ├── security.md                 # secrets, rotation runbook, approval model
│   └── runbooks/
│       └── secret-rotation.md
│
├── android/                        # Kotlin + Jetpack Compose kiosk app
│   ├── settings.gradle.kts
│   ├── gradle/libs.versions.toml   # version catalog (pinned)
│   ├── gradlew / gradlew.bat / gradle/wrapper/
│   └── app/
│       └── src/main/java/.../{ui,record,stt,net,auth,model}/
│
├── backend/
│   ├── pyproject.toml              # uv/poetry; pinned + lockfile committed
│   ├── uv.lock
│   ├── .env.example
│   ├── Dockerfile
│   ├── alembic.ini
│   └── src/pocket/
│       ├── api/                    # FastAPI routers + request/response schemas
│       ├── core/                   # config, logging, security, idempotency, errors
│       ├── domain/                 # tasks, notes, approvals, reminders logic
│       ├── integrations/           # interfaces + real + MOCK adapters
│       │   ├── llm/ (claude, openai, mock)
│       │   ├── gmail/ (real, mock)
│       │   ├── calendar/ (ics, google, mock)
│       │   ├── github/ (real, mock)
│       │   ├── claudecode/ (worker, mock)
│       │   └── stt/ (server_stt, mock)
│       ├── workers/                # interpret, execute, reminders, escalation, cc-jobs
│       ├── db/                     # models, session, migrations/
│       ├── schemas/                # shared Pydantic schemas = LLM action contract
│       └── media/                  # filesystem media-store abstraction
│   └── tests/
│       ├── unit/  integration/  contract/
│       └── fixtures/               # sanitized fixtures only (safe .ics, etc.)
│
├── shared/
│   └── action-schema/              # canonical JSON schema for proposed actions
│                                   # (source of truth shared by backend + app)
│
├── deploy/
│   ├── docker-compose.yml          # api, worker, db, redis, proxy, media volume
│   ├── docker-compose.override.example.yml
│   └── caddy/ (or traefik/)        # reverse proxy + TLS config (no secrets)
│
└── scripts/
    ├── sync-to-mini.sh             # rsync/git deploy helper (no hardcoded secrets)
    ├── dev-up.sh                   # local stack with mocks
    └── seed-dev-data.sh            # safe sample data for dev
```

---

### Appendix A — Action schema sketch (illustrative, not final)

```jsonc
{
  "actions": [
    {
      "type": "create_task",
      "explanation": "Create a normal-priority task to add logging to the new website.",
      "sensitivity": "normal",
      "payload": {
        "title": "Implement logging in the new website",
        "priority": "normal",
        "due_at": null,
        "tags": ["website", "logging"]
      }
    },
    {
      "type": "create_github_issue",
      "explanation": "Open an issue in <repo> describing the DB data-pull problem.",
      "sensitivity": "approval",
      "payload": { "repo": "OWNER/day-trader-site", "title": "...", "body": "..." }
    },
    {
      "type": "invoke_cc_job",
      "explanation": "Run Claude Code to attempt a fix on a new branch (no merge).",
      "sensitivity": "pin_required",
      "payload": { "repo": "OWNER/day-trader-site", "prompt_ref": "<prepared-job-id>" }
    }
  ]
}
```

---

*End of DESIGN.md (v0.1). This is a design artifact only; no implementation, credentials,
external calls, remote changes, or migrations were performed.*
