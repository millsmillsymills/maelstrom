#!/usr/bin/env bash
set -euo pipefail

# Scan working tree for banned GitHub auth patterns.

paths=(.)
rc=0

grep -RInE --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
  'gh auth login|github\.com/.+@|Authorization: (token|Basic)|\.netrc|getpass\(|read -s|git credential' \
  "${paths[@]}" || rc=$?

if [[ $rc -eq 0 ]]; then
  echo "Banned GitHub auth patterns detected. Please remove them and use internal/github_auth." >&2
  exit 1
fi
exit 0

