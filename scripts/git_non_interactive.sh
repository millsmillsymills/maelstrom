#!/usr/bin/env bash
set -euo pipefail

# Run git commands non-interactively against GitHub using ephemeral GIT_ASKPASS.
# Usage: scripts/git_non_interactive.sh <git-args...>

PROJ_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ASKPASS="${PROJ_ROOT}/internal/github_auth/git_askpass.sh"
if [[ ! -x "$ASKPASS" ]]; then
  echo "git_askpass.sh not found; expected at internal/github_auth/git_askpass.sh" >&2
  exit 1
fi

GIT_ASKPASS="$ASKPASS" \
GIT_TERMINAL_PROMPT=0 \
git -c credential.helper= -c http.https://github.com/.extraheader= "$@"

