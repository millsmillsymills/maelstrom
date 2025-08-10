#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

# github_auth.sh (non-interactive)
# Exposes ephemeral Git auth via GIT_ASKPASS using the central token provider.
# Usage:
#   source scripts/github_auth.sh   # sets GIT_ASKPASS and clears credential.helper for this session
#
# Behavior:
#   - Does NOT persist any git config (no extraheader written)
#   - Uses internal/github_auth/token_provider.sh to supply password (token)
#   - Username is 'x-access-token'

_exit_or_return() { local code="$1"; if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then return "$code"; else exit "$code"; fi; }

# Load .env if present (ignore comments/blank lines; tolerate absence)
if [[ -f .env ]]; then
  for _name in GITHUB_TOKEN OAUTH_ACCESS_TOKEN GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET; do
    _val=$(sed -n -e "s/^[[:space:]]*${_name}[[:space:]]*=[[:space:]]*//p" .env | tail -n1 | tr -d '\r')
    # strip surrounding quotes
    _val="${_val%\"}"; _val="${_val#\"}"; _val="${_val%\'}"; _val="${_val#\'}"
    if [[ -n "${_val}" ]]; then export "${_name}=${_val}"; fi
  done
fi

PROJ_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ASKPASS="${PROJ_ROOT}/internal/github_auth/git_askpass.sh"
if [[ ! -x "$ASKPASS" ]]; then
  echo "git_askpass.sh not found; expected at internal/github_auth/git_askpass.sh" >&2
  _exit_or_return 1
fi

# Clear any credential helper for safety in this shell; do not persist
export GIT_ASKPASS="$ASKPASS"
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes'
export GIT_CURL_VERBOSE=0

echo "Configured ephemeral GitHub auth via GIT_ASKPASS (no persistence)."
_exit_or_return 0
