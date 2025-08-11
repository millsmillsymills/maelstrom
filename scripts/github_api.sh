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
AUTH_HEADER=""
if [[ -x "$TOKEN_PROVIDER" ]]; then
  if header="$($TOKEN_PROVIDER --print-header 2>/dev/null)"; then
    AUTH_HEADER="$header"
  fi
fi

# Build curl args allowing unauthenticated fallback when no token is available
args=(
  -sS
  -H "Accept: application/vnd.github+json"
  -H "X-GitHub-Api-Version: 2022-11-28"
)
if [[ -n "$AUTH_HEADER" ]]; then
  args+=( -H "$AUTH_HEADER" )
fi

curl "${args[@]}" "$@"
