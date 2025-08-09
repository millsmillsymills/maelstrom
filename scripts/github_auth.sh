#!/usr/bin/env bash
set -euo pipefail

# github_auth.sh
# Configures repo-local GitHub auth using a bearer token and prints key presence.
# Usage:
#   scripts/github_auth.sh [--require-token]
# Behavior:
#   - Loads .env if present (safe parse)
#   - Selects EFFECTIVE_TOKEN from first non-empty of GITHUB_TOKEN, OAUTH_ACCESS_TOKEN
#   - Configures repo-local git auth header if token present; clears it otherwise
#   - Sets user identity locally

require_token=false
if [[ "${1:-}" == "--require-token" ]]; then
  require_token=true
fi

# Load .env if present (ignore comments/blank lines; tolerate absence)
if [[ -f .env ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^\s*#' .env | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | xargs -d '\n') || true
fi

# Determine token
EFFECTIVE_TOKEN="${GITHUB_TOKEN:-}"
if [[ -z "${EFFECTIVE_TOKEN}" ]]; then
  EFFECTIVE_TOKEN="${OAUTH_ACCESS_TOKEN:-}"
fi
export EFFECTIVE_TOKEN

# Print presence (never values)
printf 'GITHUB_TOKEN: %s\n' "$([[ -n "${GITHUB_TOKEN:-}" ]] && echo '[present]' || echo '[absent]')"
printf 'OAUTH_ACCESS_TOKEN: %s\n' "$([[ -n "${OAUTH_ACCESS_TOKEN:-}" ]] && echo '[present]' || echo '[absent]')"
printf 'EFFECTIVE_TOKEN: %s\n' "$([[ -n "${EFFECTIVE_TOKEN:-}" ]] && echo '[present]' || echo '[absent]')"

# Configure repo-local auth
git config --local credential.helper ""

if [[ -n "${EFFECTIVE_TOKEN}" ]]; then
  git config --local http.https://github.com/.extraheader "Authorization: Bearer ${EFFECTIVE_TOKEN}"
else
  # Ensure we don't leave stale headers behind
  git config --local --unset-all http.https://github.com/.extraheader 2>/dev/null || true
fi

# Identity
git config --local user.name  "millsmillsymills"
git config --local user.email "mills@millsymills.com"

if $require_token && [[ -z "${EFFECTIVE_TOKEN}" ]]; then
  echo "No token available; private access requires a token." >&2
  exit 1
fi

exit 0

