#!/usr/bin/env bash
# UniFi Data Export wrapper

set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [exporter args]

Wrapper around scripts/unifi/unifi_export.py. It will:
  - Source repo .env if present (for UNIFI_* / UP_UNIFI_* vars)
  - Use .venv/python if available, else system python3

Examples:
  $ scripts/unifi/unifi_export.sh --resources devices,clients --format both \\
      --since 48h --out-dir output/unifi/latest

Environment (either set or via .env):
  UNIFI_URL | UP_UNIFI_URL
  UNIFI_USER | UP_UNIFI_USERNAME
  UNIFI_PASS | UP_UNIFI_PASSWORD
  UNIFI_SITE (default: default)
  UNIFI_INSECURE | UP_UNIFI_INSECURE (true/false)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage; exit 0;;
    *) break;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"
if [[ -f "${REPO_ROOT}/scripts/util/env_aliases.sh" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/scripts/util/env_aliases.sh" && env_aliases_load
else
  if [[ -f "${REPO_ROOT}/.env" ]]; then
    set -a; set +u; set +e
    # shellcheck disable=SC1090
    source "${REPO_ROOT}/.env" 2>/dev/null || true
    set -e; set -u; set +a
  fi
fi

PY="python3"
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PY="${REPO_ROOT}/.venv/bin/python"
fi

REQS="${REPO_ROOT}/scripts/unifi/requirements.txt"
if [[ -f "$REQS" ]]; then
  # Best-effort ensure requirements are present in current interpreter
  "$PY" -c "import importlib, sys; importlib.import_module('requests')" 2>/dev/null || {
    echo "Installing UniFi toolkit requirements into current interpreter..." >&2
    "$PY" -m pip install -r "$REQS" >/dev/null
  }
fi

exec "$PY" "${REPO_ROOT}/scripts/unifi/unifi_export.py" "$@"
