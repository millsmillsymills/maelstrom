#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

# github_api.sh
# Thin wrapper over GitHub REST API with shared token selection.
# Usage:
#   scripts/github_api.sh <curl-args...>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJ_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# Resolve token non-interactively via central provider
TOKEN_PROVIDER="${PROJ_ROOT}/internal/github_auth/token_provider.sh"
if [[ ! -x "$TOKEN_PROVIDER" ]]; then
  echo "token_provider.sh not found; expected at internal/github_auth/token_provider.sh" >&2
  exit 1
fi

AUTH_HEADER="$($TOKEN_PROVIDER --print-header)"
curl -sS \
  -H "$AUTH_HEADER" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "$@"
