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

# Build curl args allowing unauthenticated fallback for READS; require auth for WRITES
args=(
  -sS
  -H "Accept: application/vnd.github+json"
  -H "X-GitHub-Api-Version: 2022-11-28"
)
if [[ -n "$AUTH_HEADER" ]]; then
  args+=( -H "$AUTH_HEADER" )
fi

# If this looks like a write call and we lack auth, fail fast with guidance
if [[ -z "$AUTH_HEADER" ]]; then
  # naive method detection from args; default is GET
  method="GET"
  for i in "$@"; do
    if [[ "$i" == "-X" ]]; then
      method="SET" # next item will hold method name
      continue
    fi
    if [[ "$method" == "SET" ]]; then
      method="$i"; break
    fi
  done
  case "$method" in
    POST|PATCH|PUT|DELETE)
      echo "error: authentication required for GitHub API $method but no token is available (set GITHUB_TOKEN/GITHUB_PAT or OAuth vars in .env)" >&2
      exit 1
      ;;
  esac
fi

curl "${args[@]}" "$@"
