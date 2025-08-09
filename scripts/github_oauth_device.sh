#!/usr/bin/env bash
set -euo pipefail

# github_oauth_device.sh
# Implements GitHub OAuth Device Authorization Grant to obtain OAUTH_ACCESS_TOKEN.
# No secrets are printed; only presence is reported. Token saved to .auth/github_oauth.env (0600).
#
# Usage:
#   scripts/github_oauth_device.sh [--scopes "repo"] [--print-only]

SCOPES="repo"
PRINT_ONLY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scopes)
      SCOPES="$2"; shift 2;;
    --print-only)
      PRINT_ONLY=true; shift;;
    *)
      echo "Unknown option: $1" >&2; exit 1;;
  esac
done

# Load env safely
if [[ -f .env ]]; then
  for _name in GITHUB_TOKEN OAUTH_ACCESS_TOKEN GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET; do
    _val=$(sed -n -e "s/^[[:space:]]*${_name}[[:space:]]*=[[:space:]]*//p" .env | tail -n1 | tr -d '\r')
    _val="${_val%\"}"; _val="${_val#\"}"; _val="${_val%\'}"; _val="${_val#\'}"
    if [[ -n "${_val}" ]]; then export "${_name}=${_val}"; fi
  done
fi

CLIENT_ID="${GITHUB_CLIENT_ID:-}"
CLIENT_SECRET_PRESENT="$([[ -n "${GITHUB_CLIENT_SECRET:-}" ]] && echo '[present]' || echo '[absent]')"

printf 'GITHUB_CLIENT_ID: %s\n' "$([[ -n "${CLIENT_ID}" ]] && echo '[present]' || echo '[absent]')"
printf 'GITHUB_CLIENT_SECRET: %s\n' "${CLIENT_SECRET_PRESENT}"

if [[ -z "${CLIENT_ID}" ]]; then
  echo "GITHUB_CLIENT_ID is required in .env for device flow." >&2
  exit 1
fi

mkdir -p .auth

# Start device authorization
resp=$(curl -sS -X POST \
  -H 'Accept: application/json' \
  -d "client_id=${CLIENT_ID}&scope=${SCOPES}" \
  https://github.com/login/device/code)

device_code=$(python3 - "$resp" << 'PY'
import json, sys
data=json.loads(sys.argv[1])
print(data.get('device_code',''))
PY
)
user_code=$(python3 - "$resp" << 'PY'
import json, sys
data=json.loads(sys.argv[1])
print(data.get('user_code',''))
PY
)
verification_uri=$(python3 - "$resp" << 'PY'
import json, sys
data=json.loads(sys.argv[1])
print(data.get('verification_uri',''))
PY
)
interval=$(python3 - "$resp" << 'PY'
import json, sys
data=json.loads(sys.argv[1])
print(int(data.get('interval', 5)))
PY
)

if [[ -z "${device_code}" || -z "${user_code}" || -z "${verification_uri}" ]]; then
  echo "Failed to initiate device authorization." >&2
  echo "$resp" >&2
  exit 1
fi

echo "Authorize this device: ${verification_uri}"
echo "Enter code: ${user_code}"

if ${PRINT_ONLY}; then
  echo "Printed verification code only (no polling)."
  exit 0
fi

echo "Waiting for authorization... (polling every ${interval}s)"

while true; do
  token_resp=$(curl -sS -X POST \
    -H 'Accept: application/json' \
    -d "client_id=${CLIENT_ID}&device_code=${device_code}&grant_type=urn:ietf:params:oauth:grant-type:device_code" \
    https://github.com/login/oauth/access_token)

  access_token=$(python3 - "$token_resp" << 'PY'
import json, sys
data=json.loads(sys.argv[1])
print(data.get('access_token',''))
PY
)
  error=$(python3 - "$token_resp" << 'PY'
import json, sys
data=json.loads(sys.argv[1])
print(data.get('error',''))
PY
)

  if [[ -n "${access_token}" ]]; then
    umask 177
    echo "OAUTH_ACCESS_TOKEN=${access_token}" > .auth/github_oauth.env
    echo "OAUTH_ACCESS_TOKEN saved to .auth/github_oauth.env ([present])."
    # Configure git headers via auth script
    ./scripts/github_auth.sh --require-token || true
    exit 0
  fi

  case "${error}" in
    authorization_pending)
      sleep "${interval}";;
    slow_down)
      sleep $((interval + 5));;
    access_denied)
      echo "Access denied by user." >&2; exit 1;;
    expired_token)
      echo "Device code expired. Re-run to get a new code." >&2; exit 1;;
    *)
      # Unknown error; print minimal hint and stop
      echo "Token request error: ${error}" >&2
      exit 1;;
  esac
done
