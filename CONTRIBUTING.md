# Contributing & working with Claude Code

This project is designed to be worked **one issue at a time, in a fresh session** — so you
never need to keep a single long-running chat alive. Each Claude Code session reads
[`CLAUDE.md`](./CLAUDE.md) and picks up an issue with full project context.

## The loop

1. **File it.** Open a GitHub issue (Bug report / Feature request templates). Keep each issue
   small and self-contained — one capability or one fix.
2. **Start a fresh Claude Code session** in the repo and point it at the issue, e.g.:
   > "Work on issue #12. Follow CLAUDE.md."
   The session auto-loads `CLAUDE.md` (architecture, commands, rules, deploy shape), so you
   don't re-explain anything.
3. **Branch.** `git switch -c feat/12-server-stt` (prefix `feat/`, `fix/`, or `chore/`).
4. **Implement, scoped to the issue.** Keep the quality gate green:
   - Backend: `ruff check` · `mypy src` · `bandit -q -r src` · `pytest -q`
   - Android: `./gradlew :app:assembleDebug` (and test on the Robin when relevant)
5. **PR.** Open a pull request with `Closes #12`. CI (lint/type/test/secret-scan) must pass.
   Use the PR template's verification checklist.
6. **Merge & (if needed) deploy.** Backend changes that affect the running server get
   redeployed to the mini (with approval) per [`docs/deploy-mini.md`](./docs/deploy-mini.md).

## Why this keeps context manageable

- **`CLAUDE.md`** is the durable, shared brain — each session loads it instead of inheriting a
  giant chat history. Update it when an architectural rule or workflow changes.
- **GitHub issues** are the backlog and the per-task spec. One issue = one branch = one
  session = one PR.
- **`DESIGN.md`** holds the long-form design; link to its sections from issues rather than
  restating them.

## Scope discipline

If, while working an issue, you find adjacent problems or ideas: **file a new issue**, don't
expand the current PR. Small PRs review and verify faster and keep history readable.

## Guardrails (see CLAUDE.md for the full list)

- Public repo: never commit secrets, real hostnames/IPs, audio, transcripts, or `.env`.
- The LLM only proposes; the backend validates and assigns sensitivity; sensitive actions
  require approval (and a PIN where applicable).
- ORM-only DB access, Alembic migrations, redacted logs, idempotent creates.

## Labels

`bug`, `enhancement`, plus area labels you can add as the backlog grows
(`android`, `backend`, `llm`, `integrations`, `deploy`). Phase labels (`phase-3` … `phase-7`)
map to [`DESIGN.md` §24](./DESIGN.md#24-recommended-implementation-phases).
