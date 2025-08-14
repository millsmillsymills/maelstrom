#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--since 7d] [--out-dir output/unifi/last7d]

Runs the UniFi pipeline: export -> load SQLite (normalized) -> report.
Sources .env, uses .venv/python if present, and writes outputs to the given directory.
USAGE
}

SINCE="7d"
OUT_DIR="output/unifi/last7d"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --since) SINCE="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
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
[[ -x "${REPO_ROOT}/.venv/bin/python" ]] && PY="${REPO_ROOT}/.venv/bin/python"

# Ensure Python deps for Slack/requests if missing
"$PY" -c "import requests" 2>/dev/null || "$PY" -m pip install -q requests >/dev/null || true

echo "[pipeline] Exporting since ${SINCE} -> ${OUT_DIR}"
"${REPO_ROOT}/scripts/unifi/unifi_export.sh" --resources all --format both --since "${SINCE}" --out-dir "${OUT_DIR}"

echo "[pipeline] Loading into SQLite (normalized)"
"$PY" "${REPO_ROOT}/scripts/unifi/unifi_load_sqlite.py" --export-dir "${OUT_DIR}" --db "${OUT_DIR}/unifi_export.db" --normalize

echo "[pipeline] Generating report"
"$PY" "${REPO_ROOT}/scripts/unifi/unifi_report.py" --db "${OUT_DIR}/unifi_export.db" --out-md "${OUT_DIR}/unifi_report.md" --out-json "${OUT_DIR}/unifi_report.json"

echo "[pipeline] Writing Prometheus metrics"
METRICS_OUT="${REPO_ROOT}/output/unifi/unifi_metrics.prom"
WINDOW_LABEL="${SINCE}"
"$PY" "${REPO_ROOT}/scripts/unifi/unifi_metrics.py" --report-json "${OUT_DIR}/unifi_report.json" --out "$METRICS_OUT" --window "$WINDOW_LABEL" || true

echo "[pipeline] Slack notification (if webhook configured)"
"$PY" "${REPO_ROOT}/scripts/unifi/unifi_notify_slack.py" --report-json "${OUT_DIR}/unifi_report.json" || true

echo "[pipeline] Slack upload of Markdown report (if SLACK_BOT_TOKEN/SLACK_CHANNEL configured)"
"$PY" "${REPO_ROOT}/scripts/unifi/unifi_slack_upload.py" \
  --file "${OUT_DIR}/unifi_report.md" \
  --title "UniFi 7-day Report" \
  --initial-comment "Automated nightly report" || true

echo "[pipeline] Publishing metrics to Node Exporter (if NODE_EXPORTER_TEXTFILE_DIR set)"
if [[ -n "${NODE_EXPORTER_TEXTFILE_DIR:-}" && -d "${NODE_EXPORTER_TEXTFILE_DIR:-}" ]]; then
  SRC_METRICS="${REPO_ROOT}/output/unifi/unifi_metrics.prom"
  DEST_METRICS="${NODE_EXPORTER_TEXTFILE_DIR}/unifi_metrics.prom"
  if ln -sf "$SRC_METRICS" "$DEST_METRICS" 2>/dev/null; then
    echo "Linked metrics to ${DEST_METRICS}"
  else
    cp -f "$SRC_METRICS" "$DEST_METRICS" || true
    echo "Copied metrics to ${DEST_METRICS}"
  fi
fi

echo "[pipeline] Done"
