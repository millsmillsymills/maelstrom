#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Prepare a PR from the code share mirror at /mnt/code/maelstrom_mgmt.

Usage:
  scripts/ops/prepare_mirror_pr.sh [--branch NAME] [--message MSG]

Notes:
  - If /mnt/code/maelstrom_mgmt is not a git repo, script prints init instructions.
  - If remote 'origin' is missing, script prints instructions to add it.
  - Does not force-push; safe by default.
USAGE
}

branch="chore/ops-alignment"
message="chore(ops): align CI, runbooks, and targets"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) branch="${2:-$branch}"; shift 2 ;;
    --message) message="${2:-$message}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

dir="/mnt/code/maelstrom_mgmt"
if [[ ! -d "$dir" ]]; then
  echo "Mirror directory not found: $dir" >&2
  exit 1
fi

if ! git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  cat <<INIT
The mirror is not a git repository. Initialize and add a remote:
  cd $dir
  git init
  git remote add origin <git@github.com:owner/repo.git>
  git checkout -b $branch
  git add -A && git commit -m "$message"
  git push -u origin $branch
INIT
  exit 0
fi

cd "$dir"

# Configure non-interactive GitHub auth if available
if [ -f "$OLDPWD/scripts/github_auth.sh" ]; then
  # shellcheck disable=SC1090
  . "$OLDPWD/scripts/github_auth.sh" || true
fi

# Ensure Git treats the shared dir as safe (NFS/SMB ownership)
git config --global --add safe.directory "$dir" >/dev/null 2>&1 || true
git checkout -B "$branch"
git add -A
if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "$message"
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "> Pushing branch $branch to origin"
  # Prefer Basic auth header for Git over HTTPS using token as password
  tok="${GITHUB_TOKEN:-${GITHUB_PAT:-}}"
  if [ -n "$tok" ]; then
    b64=$(printf 'x-access-token:%s' "$tok" | base64 -w0 2>/dev/null || printf 'x-access-token:%s' "$tok" | base64)
    git -c http.https://github.com/.extraheader="Authorization: Basic $b64" push -u origin "$branch"
  else
    # Fallback: try token provider (may yield Bearer; not always accepted by Git)
    hdr=""
    if [ -x "$OLDPWD/internal/github_auth/token_provider.sh" ]; then
      hdr=$("$OLDPWD/internal/github_auth/token_provider.sh" --print-header 2>/dev/null || true)
    fi
    if [ -n "$hdr" ]; then
      git -c http.https://github.com/.extraheader="$hdr" push -u origin "$branch"
    else
      git push -u origin "$branch"
    fi
  fi
  echo "Open a PR for branch: $branch"
else
  cat <<NOREMOTE
No 'origin' remote configured. Add a remote and push:
  git remote add origin <git@github.com:owner/repo.git>
  git push -u origin $branch
NOREMOTE
fi
