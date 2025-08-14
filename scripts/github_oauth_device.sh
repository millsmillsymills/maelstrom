#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

# Deprecated: Interactive device/browser OAuth is disabled.
# This wrapper verifies non-interactive auth via the central provider.

PROJ_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROVIDER="${PROJ_ROOT}/internal/github_auth/token_provider.sh"

echo "[deprecated] Device flow disabled. Using non-interactive provider..." >&2

if [[ ! -x "$PROVIDER" ]]; then
  echo "token_provider.sh not found; expected at internal/github_auth/token_provider.sh" >&2
  exit 1
fi

if "$PROVIDER" >/dev/null 2>&1; then
  echo "Non-interactive auth OK (token available)."
  exit 0
else
  echo "Non-interactive auth unavailable. Set GITHUB_OAUTH_* or GITHUB_PAT (or GITHUB_TOKEN in CI)." >&2
  exit 1
fi
