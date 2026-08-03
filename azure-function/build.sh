#!/usr/bin/env bash
# Build deploy zip for Azure Functions (uv export → requirements.txt, remote build on Azure).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STAGING="$(mktemp -d)"
ZIP_PATH="${SCRIPT_DIR}/release.zip"

cleanup() {
  rm -rf "${STAGING}"
}
trap cleanup EXIT

echo "Staging deploy package in ${STAGING}..."

cp "${SCRIPT_DIR}/function_app.py" "${STAGING}/"
cp "${SCRIPT_DIR}/host.json" "${STAGING}/"

cp -R "${SCRIPT_DIR}/labs" "${STAGING}/labs"
cp -R "${SCRIPT_DIR}/shared" "${STAGING}/shared"
mkdir -p "${STAGING}/checks/azure"
cp -R "${REPO_ROOT}/checks/azure/basic" "${STAGING}/checks/azure/basic"
touch "${STAGING}/checks/__init__.py" "${STAGING}/checks/azure/__init__.py"

find "${STAGING}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "${STAGING}" -name '*.pyc' -delete 2>/dev/null || true

cd "${REPO_ROOT}"
uv export --extra azure --frozen --no-dev --no-emit-project --no-hashes --no-annotate --no-header \
  -o "${STAGING}/requirements.txt"

# Oryx/pip: plain pins only (no env markers, no comments). Dedupe by package name
# (uv export may emit both azure-functions 1.x and 2.x after marker strip).
sed -E '/^[[:space:]]*#/d; s/ ; .*$//; /^[[:space:]]*$/d' "${STAGING}/requirements.txt" \
  | awk -F'==' '!seen[$1]++' > "${STAGING}/requirements.clean.txt"
mv "${STAGING}/requirements.clean.txt" "${STAGING}/requirements.txt"

echo "requirements.txt (first 10 lines):"
head -10 "${STAGING}/requirements.txt"

cd "${STAGING}"
rm -f "${ZIP_PATH}"
zip -r "${ZIP_PATH}" . -x "*.pyc" -x "__pycache__/*"

echo "Created ${ZIP_PATH}"
