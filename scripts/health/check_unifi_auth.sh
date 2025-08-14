#!/usr/bin/env bash
# Verify UniFi Controller authentication using .env variables

set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--json <path>] [--timeout <sec>]

Reads UniFi credentials from environment (or repo .env) and attempts
to authenticate to the UniFi Controller. Supports UniFi OS and legacy
endpoints. Exits 0 on success, non-zero on failure.

Environment variables checked (first non-empty wins):
  URL:  UP_UNIFI_URL | UNIFI_URL
  USER: UP_UNIFI_USERNAME | UNIFI_USER
  PASS: UP_UNIFI_PASSWORD | UNIFI_PASS
  INSECURE TLS: UP_UNIFI_INSECURE (true/false)
USAGE
}

JSON_OUT=""
TIMEOUT="10"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      JSON_OUT="$2"; shift 2;;
    --timeout)
      TIMEOUT="$2"; shift 2;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown option: $1" >&2; usage; exit 1;;
  esac
done

# Resolve repo root and source .env if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
if [[ -f "${REPO_ROOT}/scripts/util/env_aliases.sh" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/scripts/util/env_aliases.sh" && env_aliases_load
else
  if [[ -f "${REPO_ROOT}/.env" ]]; then
    set -a
    set +u
    set +e
    # shellcheck disable=SC1090
    source "${REPO_ROOT}/.env" 2>/dev/null || true
    set -e
    set -u
    set +a
  fi
fi

trim_trailing_slash() { echo "$1" | sed 's:/*$::'; }

URL="${UP_UNIFI_URL:-${UNIFI_URL:-}}"
USER="${UP_UNIFI_USERNAME:-${UNIFI_USER:-}}"
PASS="${UP_UNIFI_PASSWORD:-${UNIFI_PASS:-}}"
INSECURE="${UP_UNIFI_INSECURE:-false}"

if [[ -z "${URL}" || -z "${USER}" || -z "${PASS}" ]]; then
  echo "Missing UniFi credentials. Need URL, USER, PASS from .env or environment." >&2
  exit 2
fi

URL="$(trim_trailing_slash "${URL}")"

curl_opts=(
  -sS
  --max-time "${TIMEOUT}"
  -H 'Content-Type: application/json'
  -c /tmp/unifi_cookies.txt -b /tmp/unifi_cookies.txt
)
[[ "${INSECURE,,}" =~ ^(1|true|yes|on)$ ]] && curl_opts+=( -k )

# Build JSON payload safely (prefer jq, fallback to python)
if command -v jq >/dev/null 2>&1; then
  payload=$(jq -cn --arg u "$USER" --arg p "$PASS" '{username:$u, password:$p}')
elif command -v python3 >/dev/null 2>&1; then
  payload=$(UNIFI_USER_ENV="$USER" UNIFI_PASS_ENV="$PASS" python3 - <<'PY'
import os, json
print(json.dumps({
    "username": os.environ.get("UNIFI_USER_ENV", ""),
    "password": os.environ.get("UNIFI_PASS_ENV", ""),
}))
PY
  )
else
  # naive fallback (may fail if special chars present)
  payload='{"username":"'"${USER}"'","password":"'"${PASS}"'"}'
fi

# Try UniFi OS first: /api/auth/login
status_os=$(curl "${curl_opts[@]}" -o /tmp/unifi_login_os.out -w '%{http_code}' \
  -X POST "${URL}/api/auth/login" -d "${payload}" || true)

# Fallback legacy: /api/login
status_legacy=""
if [[ "${status_os}" != "200" ]]; then
  status_legacy=$(curl "${curl_opts[@]}" -o /tmp/unifi_login_legacy.out -w '%{http_code}' \
    -X POST "${URL}/api/login" -d "${payload}" || true)
fi

success=false
endpoint=""
code="${status_os}"
if [[ "${status_os}" == "200" ]]; then
  success=true
  endpoint="/api/auth/login"
elif [[ "${status_legacy}" == "200" ]]; then
  success=true
  endpoint="/api/login"
  code="${status_legacy}"
fi

if [[ -n "${JSON_OUT}" ]]; then
  mkdir -p "$(dirname "${JSON_OUT}")" || true
  jq -n --arg url "$URL" --arg user "$USER" --arg endpoint "$endpoint" \
        --arg code "$code" --arg insecure "${INSECURE}" \
        --arg status "$([[ ${success} == true ]] && echo success || echo failure)" \
        '{url:$url,user:$user,endpoint:$endpoint,http_code:$code,insecure:$insecure,status:$status}' \
        > "${JSON_OUT}" || true
fi

if [[ "${success}" == true ]]; then
  echo "UniFi authentication succeeded via ${endpoint} (HTTP ${code})"
  exit 0
else
  echo "UniFi authentication failed (OS=${status_os} legacy=${status_legacy:-n/a}). Check URL/creds and UP_UNIFI_INSECURE." >&2
  exit 1
fi
