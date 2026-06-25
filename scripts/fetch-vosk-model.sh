#!/usr/bin/env bash
# Download the small English Vosk model into the Android app's assets.
# The model (~40 MB) is NOT committed to git (see .gitignore); each builder fetches it once.
set -euo pipefail

MODEL_NAME="vosk-model-small-en-us-0.15"
MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${REPO_ROOT}/android/app/src/main/assets/model/en-us"

if [[ -f "${DEST}/.unpacked" || -d "${DEST}/am" ]]; then
  echo "Vosk model already present at ${DEST}"
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading ${MODEL_URL} ..."
curl -fL "${MODEL_URL}" -o "${TMP}/model.zip"
echo "Unzipping ..."
unzip -q "${TMP}/model.zip" -d "${TMP}"

mkdir -p "${DEST}"
cp -R "${TMP}/${MODEL_NAME}/." "${DEST}/"
echo "Installed Vosk model to ${DEST}"
