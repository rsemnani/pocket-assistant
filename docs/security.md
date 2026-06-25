# Security & approval model

See `DESIGN.md` §13–18 for the full model. This is the operator-facing summary.

## Secrets

- Real secrets live in `.env` files that are **git-ignored**. Only `*.env.example` with
  `CHANGE_ME` placeholders are committed.
- Secrets are environment-separated (`APP_ENV=dev|staging|prod`); values never cross
  environments.
- Integration tokens (Gmail, GitHub) and the device-token pepper are stored encrypted at
  rest on `@mini` and referenced by ID — never logged, never returned by the API.

## What is NEVER committed

API keys, OAuth tokens/clients, device tokens, DB passwords, SSH secrets, private
hostnames/tunnels, sensitive IPs, audio, transcripts, generated ICS, logs, audit exports.
The `.gitignore` and `.gitleaks.toml` enforce this; CI + pre-commit scan every change.

## Approval tiers

| Tier | Examples | Gate |
|---|---|---|
| normal | create task/note, propose event, daily summary | approval (dev) |
| approval | create GitHub issue, generate ICS, limited email search | explicit approval |
| pin_required | invoke Claude Code, draft/contact a person, broad email search, open uncertain attachment | approval + session PIN |

- **During development, all actions require approval.**
- A session PIN unlocks `pin_required` actions for a configurable window (default 15 min) —
  not every single action.

## Least privilege

- **Gmail:** read-only + draft-only scopes. No send scope is ever requested.
- **Calendar:** read a single private iCal feed URL (no OAuth, no write scope).
- **GitHub:** fine-grained token limited to an explicit repo allowlist
  (`GITHUB_REPO_ALLOWLIST`).
- **Claude Code:** sandboxed worker; produces a branch/PR only — never auto-merges or
  pushes to the default branch.

## If a secret is accidentally committed

Follow [`runbooks/secret-rotation.md`](./runbooks/secret-rotation.md). The short version:
**rotate first** (the value is compromised the moment it is pushed), then scrub history,
then invalidate derived tokens.
