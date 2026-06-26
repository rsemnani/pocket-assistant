#!/usr/bin/env bash
# Export raw->corrected transcript pairs as CSV, for evaluating/improving transcription.
# Usage:
#   BASE=https://robin.rtbsengineering.com DEVICE_TOKEN=pa_dev_... ./scripts/export-corrections.sh > corrections.csv
#
# DEVICE_TOKEN is a paired device token (the app stores one; or register a device).
set -euo pipefail

BASE="${BASE:?set BASE to the backend URL}"
DEVICE_TOKEN="${DEVICE_TOKEN:?set DEVICE_TOKEN to a paired device token}"

curl -fsS "${BASE%/}/v1/captures/corrections?limit=5000" \
  -H "Authorization: Bearer ${DEVICE_TOKEN}" \
| python3 -c '
import csv, json, sys
rows = json.load(sys.stdin)
w = csv.writer(sys.stdout)
w.writerow(["captured_at", "transcript_raw", "transcript_edited"])
for r in rows:
    w.writerow([r.get("captured_at") or "", r.get("transcript_raw") or "", r.get("transcript_edited") or ""])
'
