# Deploying to the home server (`@mini`)

The backend, database, workers, and media storage run on the mini computer (NucBox),
reached via SSH into its WSL environment:

```bash
ssh rs@nucboxk8plus      # lands in WSL on the Windows mini computer
```

> The Android phone is **not** connected to `@mini` — it is plugged into `@dev-pc`. The
> phone reaches the backend over the network (LAN, or Tailscale when remote).

## Deploy model

Code is authored on `@dev-pc` and **synced** to `@mini` — the server is a deploy target,
not an editor. Two options:

1. **git pull on the server** (once the repo has a remote):
   ```bash
   ssh rs@nucboxk8plus
   cd ~/pocket-assistant && git pull
   ```
2. **rsync from `@dev-pc`** (no remote needed) — see `scripts/sync-to-mini.sh`.

## Bring up the stack (`@docker` on `@mini`)

```bash
ssh rs@nucboxk8plus
cd ~/pocket-assistant/deploy
cp .env.example .env          # then fill real values on the server ONLY (never committed)
docker compose up -d --build
```

## Migrations

Run Alembic **inside the API container**, and only after reviewing the migration:

```bash
docker compose exec api uv run alembic upgrade head
```

## Media storage

Media lives on a host volume mounted into the containers at `MEDIA_ROOT` (default
`/data/media`), capped at `MEDIA_MAX_BYTES` (default 50 GB). The host path is configured via
`.env` on the server and is never committed.

## Remote access for the phone

- **On the home LAN:** the phone points at `http://<mini-lan-ip>:<port>`.
- **Remote:** join the phone and `@mini` to a **Tailscale** tailnet; the phone reaches
  `@mini` by its tailnet name. (A Cloudflare Tunnel can be added if a public HTTPS hostname
  is ever wanted.) The API is never exposed directly to the public internet.

## Safety reminders

Before changing anything on `@mini` — `docker compose`, migrations, file writes — the
operator (or Claude Code) explains the intended action and gets approval first. No real
credentials, external API calls, or migrations against a real DB happen without explicit
sign-off.
