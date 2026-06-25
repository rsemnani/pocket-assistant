#!/usr/bin/env bash
# Sync the repo to the mini computer (@mini) over SSH, excluding secrets and local junk.
# The server is a deploy target, not an editor. Configure host/dest via env, no hardcoding.
#
#   MINI_HOST=rs@nucboxk8plus MINI_DEST=~/pocket-assistant ./scripts/sync-to-mini.sh
set -euo pipefail

MINI_HOST="${MINI_HOST:-rs@nucboxk8plus}"
MINI_DEST="${MINI_DEST:-~/pocket-assistant}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Syncing ${REPO_ROOT} -> ${MINI_HOST}:${MINI_DEST}"
echo "(dry run; pass --go to actually transfer)"

RSYNC_FLAGS=(-az --delete
  --exclude '.git/'
  --exclude '.env' --exclude '.env.*'
  --exclude '.venv/' --exclude '__pycache__/'
  --exclude 'data/' --exclude '_media/' --exclude '*.sqlite3'
  --exclude 'android/build/' --exclude 'android/.gradle/')

if [[ "${1:-}" == "--go" ]]; then
  rsync "${RSYNC_FLAGS[@]}" "${REPO_ROOT}/" "${MINI_HOST}:${MINI_DEST}/"
  echo "Done. On @mini: cd ${MINI_DEST}/deploy && docker compose up -d --build"
else
  rsync "${RSYNC_FLAGS[@]}" --dry-run "${REPO_ROOT}/" "${MINI_HOST}:${MINI_DEST}/"
fi
