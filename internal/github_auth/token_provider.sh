#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh

# Central GitHub token provider (Bash)
# Priority:
#   1) OAuth2 refresh using pre-provisioned refresh token
#   2) PAT from env (GITHUB_PAT or GITHUB_TOKEN)
# With: in-memory env cache within process; optional disk cache skipped in CI.
# Outputs: prints token to stdout when invoked; can also export AUTH_HEADER if requested.

GITHUB_API_BASE="${GITHUB_API_BASE:-https://api.github.com}"
CACHE_FILE="${HOME}/.cache/github_token.json"

_now() { date +%s; }

_read_cache() {
  if [[ -n "${CI:-}" ]]; then return 1; fi
  [[ -f "$CACHE_FILE" ]] || return 1
  local exp token
  token=$(jq -r '.access_token // empty' "$CACHE_FILE" 2>/dev/null || true)
  exp=$(jq -r '.expires_at // empty' "$CACHE_FILE" 2>/dev/null || true)
  if [[ -z "$token" ]]; then return 1; fi
  if [[ -n "$exp" ]]; then
    local now=$(_now)
    # 5 minute early refresh window
    if (( exp - now <= 300 )); then return 1; fi
  fi
  printf '%s' "$token"
}

_write_cache() {
  if [[ -n "${CI:-}" ]]; then return 0; fi
  mkdir -p "$(dirname "$CACHE_FILE")"
  umask 177
  printf '%s' "$1" | jq -c --arg now "$(date +%s)" '{access_token:., token_type:"bearer", expires_at:null, source:"bash"}' >"$CACHE_FILE.tmp" 2>/dev/null || true
  mv -f "$CACHE_FILE.tmp" "$CACHE_FILE" 2>/dev/null || true
}

_oauth_refresh() {
  local cid="${GITHUB_OAUTH_CLIENT_ID:-}" csec="${GITHUB_OAUTH_CLIENT_SECRET:-}" rtok="${GITHUB_OAUTH_REFRESH_TOKEN:-}"
  if [[ -z "$cid" || -z "$csec" || -z "$rtok" ]]; then return 1; fi
  local resp
  resp=$(curl -sS --fail -X POST \
    -H 'Accept: application/json' -H 'Content-Type: application/json' \
    -d "{\"grant_type\":\"refresh_token\",\"refresh_token\":\"$rtok\",\"client_id\":\"$cid\",\"client_secret\":\"$csec\"}" \
    https://github.com/login/oauth/access_token) || return 1
  local token exp
  token=$(jq -r '.access_token // empty' <<<"$resp")
  exp=$(jq -r '.expires_in // empty' <<<"$resp")
  if [[ -z "$token" ]]; then return 1; fi
  # compute expires_at if provided (not strictly needed here)
  if [[ -n "$exp" && "$exp" =~ ^[0-9]+$ ]]; then
    local now=$(_now)
    local expires_at=$(( now + exp ))
    jq -c --arg t "$token" --argjson ea "$expires_at" '{access_token:$t, token_type:"bearer", expires_at:$ea, source:"oauth"}' >/dev/null <<<"{}" || true
  fi
  printf '%s' "$token"
}

_probe() {
  local token="$1"
  curl -sS -o /dev/null -w '%{http_code}' \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    -H "Authorization: Bearer $token" \
    "$GITHUB_API_BASE/rate_limit" || printf '0'
}

get_access_token() {
  local t
  t=$(_read_cache || true)
  if [[ -n "$t" ]]; then
    local code
    code=$(_probe "$t")
    if [[ "$code" == "200" || "$code" == "304" ]]; then
      printf '%s' "$t"; return 0
    fi
  fi

  # Try OAuth refresh
  t=$(_oauth_refresh || true)
  if [[ -n "$t" ]]; then
    for i in 0 1 2; do
      local code
      code=$(_probe "$t")
      if [[ "$code" == "200" || "$code" == "304" ]]; then
        _write_cache "$t" || true
        printf '%s' "$t"; return 0
      fi
      sleep "$(( (RANDOM % 250 + 250 + (1<<i)*1000) / 1000 ))" 2>/dev/null || sleep 1
    done
  fi

  # Fallback to PAT
  t="${GITHUB_PAT:-${GITHUB_TOKEN:-}}"
  if [[ -n "$t" ]]; then
    for i in 0 1 2; do
      local code
      code=$(_probe "$t")
      if [[ "$code" == "200" || "$code" == "304" ]]; then
        printf '%s' "$t"; return 0
      fi
      sleep "$(( (RANDOM % 250 + 250 + (1<<i)*1000) / 1000 ))" 2>/dev/null || sleep 1
    done
  fi
  echo "error: unable to obtain GitHub token non-interactively" >&2
  return 1
}

if [[ "${1:-}" == "--print-header" ]]; then
  tok=$(get_access_token)
  printf 'Authorization: Bearer %s' "$tok"
  exit 0
fi

# Default behavior: print token
get_access_token