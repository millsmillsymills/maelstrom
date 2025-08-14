#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Check PRs for this repository via GitHub API.

Usage:
  scripts/ops/check_prs.sh [--state open|closed|all]

Environment:
  - Uses internal/github_auth/token_provider.sh to obtain a token if available.

Output:
  - Prints a concise table: number, state, title, updated_at.
USAGE
}

state="open"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --state) state="${2:-open}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

remote_url=$(git config --get remote.origin.url || true)
if [[ -z "$remote_url" ]]; then echo "No git remote.origin.url configured" >&2; exit 1; fi

# Extract owner/repo from common URL forms
repo_path=$(sed -E 's#.*github.com[:/](.+/[^.]+)(\.git)?$#\1#' <<<"$remote_url")
if [[ -z "$repo_path" || "$repo_path" == "$remote_url" ]]; then
  echo "Unable to parse GitHub repo from $remote_url" >&2; exit 1
fi

base="https://api.github.com/repos/$repo_path/pulls?state=$state&per_page=100"

auth_header=""
if [[ -x internal/github_auth/token_provider.sh ]]; then
  if hdr=$(internal/github_auth/token_provider.sh --print-header 2>/dev/null); then
    auth_header="-H '$hdr'"
  fi
fi

cmd="curl -sS -m 8 -H 'Accept: application/vnd.github+json' -H 'X-GitHub-Api-Version: 2022-11-28' $auth_header '$base'"
resp=$(eval "$cmd" 2>/dev/null || true)
if [[ -z "$resp" ]]; then
  echo "No response from GitHub API (network or auth issue)." >&2
  exit 0
fi
RESP="$resp" python3 - <<'PY'
import os, sys, json
try:
    payload = os.environ.get('RESP', '')
    data = json.loads(payload or '[]')
except Exception as e:
    print(f"error: unable to parse response: {e}")
    sys.exit(0)
if isinstance(data, dict) and 'message' in data:
    print(f"error: {data['message']}")
    sys.exit(0)
print(f"# PRs ({len(data)})\n")
print("| # | state | title | updated |")
print("|---|-------|--------|---------|")
for pr in data:
    num = pr.get('number')
    st = pr.get('state')
    title = pr.get('title','').replace('\n',' ')
    upd = pr.get('updated_at')
    print(f"| {num} | {st} | {title} | {upd} |")
PY
