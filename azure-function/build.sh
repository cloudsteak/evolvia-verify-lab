#!/usr/bin/env bash
# Build deploy zip for Azure Functions (uv + pyproject.toml, like the Docker image).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STAGING="$(mktemp -d)"
ZIP_PATH="${SCRIPT_DIR}/release.zip"
PYTHON_VERSION="3.12"

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
rm -rf "${STAGING}/checks/azure/basic/__pycache__"
touch "${STAGING}/checks/__init__.py" "${STAGING}/checks/azure/__init__.py"

cd "${REPO_ROOT}"
uv export --extra azure --frozen --no-dev --no-emit-project --no-hashes \
  -o "${STAGING}/requirements.txt"

uv pip install \
  --python "${PYTHON_VERSION}" \
  --target "${STAGING}/.python_packages/lib/site-packages" \
  -r "${STAGING}/requirements.txt"

rm "${STAGING}/requirements.txt"

cd "${STAGING}"
zip -r "${ZIP_PATH}" . -x "*.pyc" -x "__pycache__/*"

echo "Created ${ZIP_PATH}"
