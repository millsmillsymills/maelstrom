#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--grafana-url http://localhost:3000] [--user admin] [--pass ...] [--folder-id 0]

Imports docs/dashboards/unifi_overview.json into Grafana via the HTTP API.
Reads credentials from .env if available.
USAGE
}

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
if [[ -f "$REPO/scripts/util/env_aliases.sh" ]]; then
  # shellcheck disable=SC1090
  source "$REPO/scripts/util/env_aliases.sh" && env_aliases_load
fi

URL="${GRAFANA_URL:-http://localhost:3000}"
# Accept a variety of env names for admin creds
USER="${GF_SECURITY_ADMIN_USER:-${GRAFANA_USERNAME:-${GRAFANA_ADMIN_USER:-admin}}}"
PASS="${GF_SECURITY_ADMIN_PASSWORD:-${GRAFANA_PASSWORD:-${GRAFANA_ADMIN_PASS:-admin}}}"
FOLDER_ID=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --grafana-url) URL="$2"; shift 2 ;;
    --user) USER="$2"; shift 2 ;;
    --pass) PASS="$2"; shift 2 ;;
    --folder-id) FOLDER_ID="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

DASH_JSON="$REPO/docs/dashboards/unifi_overview.json"

if [[ ! -f "$DASH_JSON" ]]; then
  echo "Dashboard JSON not found: $DASH_JSON" >&2
  exit 2
fi

payload=$(jq -nc --argjson dashboard "$(cat "$DASH_JSON")" --arg folderId "$FOLDER_ID" '{dashboard:$dashboard, overwrite:true, folderId: ($folderId|tonumber)}')

echo "Importing dashboard to $URL ..."
curl -sS -u "$USER:$PASS" -H 'Content-Type: application/json' \
  -X POST "$URL/api/dashboards/db" -d "$payload" | jq .
