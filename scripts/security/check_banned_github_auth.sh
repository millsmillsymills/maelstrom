#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

# Scan working tree for banned GitHub auth patterns.

paths=(.)
rc=0

# Default excludes to avoid false positives from generated artifacts and caches
EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=node_modules
  --exclude-dir=.venv
  --exclude-dir=reports
  --exclude-dir=output
  --exclude-dir=.cache
  --exclude-dir=.codex
  --exclude-dir=.npm
)

grep -RInE "${EXCLUDES[@]}" \
  'gh auth login|github\.com/.+@|Authorization: (token|Basic)|\.netrc|getpass\(|read -s|git credential' \
  "${paths[@]}" || rc=$?

if [[ $rc -eq 0 ]]; then
  echo "Banned GitHub auth patterns detected. Please remove them and use internal/github_auth." >&2
  exit 1
fi
exit 0
