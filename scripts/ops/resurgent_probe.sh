#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Resurgent Probe Runbook (dry-run by default)

Description:
  Detects whether the Resurgent host exposes endpoints over HTTPS with valid TLS,
  HTTPS with self-signed (insecure), or HTTP, and suggests .env entries.
  Also enables all RESURGENT_ENABLE_* toggles. With --apply, updates .env safely.

Usage:
  scripts/ops/resurgent_probe.sh [--apply] [--host HOSTNAME] [--ip IP]

Environment:
  RESURGENT_HOST / RESURGENT_IP
  Optional custom ports: RESURGENT_*_PORT (node:9100, cadvisor:8081, grafana:3000, prometheus:9090, diagnostics:8080)

Output:
  Recommended .env entries. Use --apply to write them.
USAGE
}

apply=false
host="${RESURGENT_HOST:-}"
ip="${RESURGENT_IP:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) apply=true; shift ;;
    --host) host="${2:-}"; shift 2 ;;
    --ip) ip="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$host" && -z "$ip" ]]; then
  echo "Provide --host or --ip (or set RESURGENT_HOST/RESURGENT_IP)." >&2
  exit 1
fi

target_host="${host:-$ip}"

NODE_EXPORTER_PORT="${RESURGENT_NODE_EXPORTER_PORT:-9100}"
CADVISOR_PORT="${RESURGENT_CADVISOR_PORT:-8081}"
GRAFANA_PORT="${RESURGENT_GRAFANA_PORT:-3000}"
PROM_PORT="${RESURGENT_PROMETHEUS_PORT:-9090}"
DIAG_PORT="${RESURGENT_DIAGNOSTICS_PORT:-8080}"

# Candidate endpoints: tuple of port and path
endpoints=(
  "$GRAFANA_PORT:/api/health"
  "$PROM_PORT:/-/ready"
  "$NODE_EXPORTER_PORT:/metrics"
  "$CADVISOR_PORT:/metrics"
  "$DIAG_PORT:/api/diagnostics"
)

scheme="http"
verify_tls="false"

probe() {
  local proto="$1" insecure_flag="$2" p path url
  for e in "${endpoints[@]}"; do
    p="${e%%:*}"; path="${e#*:}"
    url="${proto}://${target_host}:${p}${path}"
    if curl -fsS -m 4 $insecure_flag "$url" >/dev/null 2>&1; then
      echo "$proto $insecure_flag $url"; return 0
    fi
  done
  return 1
}

if out=$(probe https ""); then
  scheme="https"; verify_tls="true"
elif out=$(probe https "-k"); then
  scheme="https"; verify_tls="false"
elif out=$(probe http ""); then
  scheme="http"; verify_tls="false"
else
  echo "Warning: Unable to reach any known endpoints on ${target_host}. Falling back to http with verify=false." >&2
  scheme="http"; verify_tls="false"
fi

echo ":: Resurgent probe results ::"
echo "Host: ${target_host}"
echo "Detected scheme: ${scheme} (verify_tls=${verify_tls})"

reco=$(cat <<ENV
RESURGENT_HOST=${host}
RESURGENT_IP=${ip}
RESURGENT_USE_HTTPS=$([[ "$scheme" == "https" ]] && echo true || echo false)
RESURGENT_VERIFY_TLS=$verify_tls
RESURGENT_NODE_EXPORTER_PORT=${NODE_EXPORTER_PORT}
RESURGENT_CADVISOR_PORT=${CADVISOR_PORT}
RESURGENT_GRAFANA_PORT=${GRAFANA_PORT}
RESURGENT_PROMETHEUS_PORT=${PROM_PORT}
RESURGENT_DIAGNOSTICS_PORT=${DIAG_PORT}
RESURGENT_ENABLE_NODE_EXPORTER=true
RESURGENT_ENABLE_CADVISOR=true
RESURGENT_ENABLE_GRAFANA=true
RESURGENT_ENABLE_PROMETHEUS=true
RESURGENT_ENABLE_DIAGNOSTICS=true
ENV
)

echo "\nRecommended .env entries:" && echo "$reco"

if $apply; then
  if [[ -f .env ]]; then cp -p .env ".env.backup.$(date +%Y%m%d-%H%M%S)"; fi
  while IFS='=' read -r k v; do
    [[ -z "$k" ]] && continue
    if grep -qE "^${k}=" .env 2>/dev/null; then
      sed -i -E "s|^${k}=.*|${k}=${v}|" .env
    else
      echo "${k}=${v}" >> .env
    fi
  done <<< "$reco"
  echo "Applied recommendations to .env (backup created if file existed)."
else
  echo "(Dry-run) Use --apply to write these to .env"
fi
