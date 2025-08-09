#!/usr/bin/env bash
set -euo pipefail

# Ephemeral GIT_ASKPASS that returns the OAuth/PAT token as password.
# Username should be set to 'x-access-token' when invoking git.

HERE="$(cd "$(dirname "$0")" && pwd)"
TOK=$("${HERE}/token_provider.sh")

case "${1:-}" in
  *username*)
    printf '%s' 'x-access-token'
    ;;
  *password*)
    printf '%s' "$TOK"
    ;;
  *)
    printf ''
    ;;
esac

