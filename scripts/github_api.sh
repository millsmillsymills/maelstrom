#!/usr/bin/env bash
set -euo pipefail

# github_api.sh
# Thin wrapper over GitHub REST API with shared token selection.
# Usage:
#   scripts/github_api.sh <curl-args...>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source auth to populate EFFECTIVE_TOKEN and env from .env, but do not require token unless we need it here.
# This will also configure git headers, which is acceptable and idempotent.
"${SCRIPT_DIR}/github_auth.sh" >/dev/null || true

EFFECTIVE_TOKEN="${EFFECTIVE_TOKEN:-${GITHUB_TOKEN:-${OAUTH_ACCESS_TOKEN:-}}}"
if [[ -z "${EFFECTIVE_TOKEN}" ]]; then
  echo "GitHub token is required for API calls." >&2
  exit 1
fi

curl -sS \
  -H "Authorization: Bearer ${EFFECTIVE_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "$@"

