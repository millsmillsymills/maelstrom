#!/usr/bin/env bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
set -euo pipefail

# Scan working tree for banned GitHub auth patterns.

# Limit scan to tracked files if inside a git work tree to avoid host noise
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  mapfile -t paths < <(git ls-files)
else
  paths=(.)
fi
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
  --exclude-dir=backups
  --exclude-dir=.local
  --exclude-dir=.nvm
)

# Restrict to relevant file types
PATTERN='(\.sh|\.bash|\.zsh|\.ps1|\.py|\.js|\.ts|\.go|\.rb|\.rs|\.java|\.gradle|\.groovy|\.php|\.pl|\.yml|\.yaml|\.json|(^|/)Makefile$|\.mk|\.toml|\.ini|(^|/)Dockerfile[^/]*$|(^|/)docker-compose[^/]*\.yml$|(^|/)\.env|(^|/)\.pre-commit-config\.yaml$|(^|/)\.gitmodules$)'
mapfile -t scan_files < <(printf '%s\n' "${paths[@]}" | grep -E "$PATTERN" || true)

# Exclude this script itself from scanning to avoid self-matching
scan_files=("${scan_files[@]/scripts\/security\/check_banned_github_auth.sh}")

if [[ ${#scan_files[@]} -eq 0 ]]; then
  exit 0
fi

grep -nE 'gh auth login|github\.com/.+@|\.netrc|read -s|git credential' \
  "${scan_files[@]}" || rc=$?

if [[ $rc -eq 0 ]]; then
  echo "Banned GitHub auth patterns detected. Please remove them and use internal/github_auth." >&2
  exit 1
fi
exit 0
