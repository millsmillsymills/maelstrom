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

_exit_or_return() {
  local code="$1"
  # If script is sourced, return; else exit
  if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return "$code"
  else
    exit "$code"
  fi
}

# Load .env if present (ignore comments/blank lines; tolerate absence)
if [[ -f .env ]]; then
  for _name in GITHUB_TOKEN OAUTH_ACCESS_TOKEN GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET; do
    _val=$(sed -n -e "s/^[[:space:]]*${_name}[[:space:]]*=[[:space:]]*//p" .env | tail -n1 | tr -d '\r')
    # strip surrounding quotes
    _val="${_val%\"}"; _val="${_val#\"}"; _val="${_val%\'}"; _val="${_val#\'}"
    if [[ -n "${_val}" ]]; then export "${_name}=${_val}"; fi
  done
fi

# Also load OAuth token if previously obtained via device flow
if [[ -f .auth/github_oauth.env ]]; then
  # shellcheck disable=SC1091
  source .auth/github_oauth.env || true
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
  # For Git operations, GitHub expects Basic with token as password.
  b64=$(printf 'x-access-token:%s' "${EFFECTIVE_TOKEN}" | base64 | tr -d '\n')
  git config --local http.https://github.com/.extraheader "Authorization: Basic ${b64}"
else
  # Ensure we don't leave stale headers behind
  git config --local --unset-all http.https://github.com/.extraheader 2>/dev/null || true
fi

# Identity
git config --local user.name  "millsmillsymills"
git config --local user.email "mills@millsymills.com"

if $require_token && [[ -z "${EFFECTIVE_TOKEN}" ]]; then
  echo "No token available; private access requires a token." >&2
  _exit_or_return 1
fi

_exit_or_return 0
