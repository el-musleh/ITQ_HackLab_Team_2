#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.gemini"

echo "Deploying Gemini CLI + Antigravity permission configs..."

mkdir -p "${TARGET_DIR}/policies"
mkdir -p "${TARGET_DIR}/antigravity/policies"

cp -f "${SCRIPT_DIR}/settings.json"       "${TARGET_DIR}/settings.json"
cp -f "${SCRIPT_DIR}/auto-saved.toml"    "${TARGET_DIR}/policies/auto-saved.toml"
cp -f "${SCRIPT_DIR}/trustedFolders.json" "${TARGET_DIR}/trustedFolders.json"

cp -f "${SCRIPT_DIR}/antigravity-settings.json"       "${TARGET_DIR}/antigravity/settings.json"
cp -f "${SCRIPT_DIR}/antigravity-auto-saved.toml"    "${TARGET_DIR}/antigravity/policies/auto-saved.toml"

echo "Done. Installed to:"
echo "  Gemini CLI:"
echo "    ${TARGET_DIR}/settings.json"
echo "    ${TARGET_DIR}/policies/auto-saved.toml"
echo "    ${TARGET_DIR}/trustedFolders.json"
echo "  Antigravity:"
echo "    ${TARGET_DIR}/antigravity/settings.json"
echo "    ${TARGET_DIR}/antigravity/policies/auto-saved.toml"
echo ""
echo "Restart any running agy / Gemini CLI / Antigravity sessions for changes to take effect."
