#!/usr/bin/env bash
# Normalize env var aliases across legacy/new names.
# Safe to source with strict mode callers; internally relaxes while reading .env.

_ea_repo_root() {
  local D="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"; echo "$D";
}

env_aliases_load() {
  local REPO_ROOT; REPO_ROOT="$(_ea_repo_root)"
  if [[ -f "$REPO_ROOT/.env" ]]; then
    set -a; set +u; set +e
    # shellcheck disable=SC1090
    source "$REPO_ROOT/.env" 2>/dev/null || true
    set -e; set -u; set +a
  fi

  # Grafana admin credentials: map between common names
  if [[ -z "${GRAFANA_USERNAME:-}" && -n "${GF_SECURITY_ADMIN_USER:-}" ]]; then
    export GRAFANA_USERNAME="$GF_SECURITY_ADMIN_USER"
  fi
  if [[ -z "${GRAFANA_PASSWORD:-}" && -n "${GF_SECURITY_ADMIN_PASSWORD:-}" ]]; then
    export GRAFANA_PASSWORD="$GF_SECURITY_ADMIN_PASSWORD"
  fi
  if [[ -z "${GF_SECURITY_ADMIN_USER:-}" && -n "${GRAFANA_USERNAME:-}" ]]; then
    export GF_SECURITY_ADMIN_USER="$GRAFANA_USERNAME"
  fi
  if [[ -z "${GF_SECURITY_ADMIN_PASSWORD:-}" && -n "${GRAFANA_PASSWORD:-}" ]]; then
    export GF_SECURITY_ADMIN_PASSWORD="$GRAFANA_PASSWORD"
  fi

  # Grafana URL default
  if [[ -z "${GRAFANA_URL:-}" ]]; then
    export GRAFANA_URL="http://localhost:3000"
  fi

  # UniFi aliases (prefer UP_*; backfill from legacy UNIFI_*)
  [[ -z "${UP_UNIFI_URL:-}" && -n "${UNIFI_URL:-}" ]] && export UP_UNIFI_URL="$UNIFI_URL"
  [[ -z "${UP_UNIFI_USERNAME:-}" && -n "${UNIFI_USER:-}" ]] && export UP_UNIFI_USERNAME="$UNIFI_USER"
  [[ -z "${UP_UNIFI_PASSWORD:-}" && -n "${UNIFI_PASS:-}" ]] && export UP_UNIFI_PASSWORD="$UNIFI_PASS"
  [[ -z "${UP_UNIFI_INSECURE:-}" && -n "${UNIFI_INSECURE:-}" ]] && export UP_UNIFI_INSECURE="$UNIFI_INSECURE"

  # Slack webhook alias (support SLACK_WEBHOOK and SLACK_WEBHOOK_URL)
  if [[ -z "${SLACK_WEBHOOK_URL:-}" && -n "${SLACK_WEBHOOK:-}" ]]; then
    export SLACK_WEBHOOK_URL="$SLACK_WEBHOOK"
  fi

  # Prometheus/Alertmanager common aliases for health and tools
  if [[ -z "${PROM_URL:-}" ]]; then
    if [[ -n "${PROMETHEUS_URL:-}" ]]; then
      export PROM_URL="$PROMETHEUS_URL"
    elif [[ -n "${METRICS_ENDPOINT:-}" ]]; then
      export PROM_URL="$METRICS_ENDPOINT"
    else
      export PROM_URL="http://localhost:9090"
    fi
  fi
  if [[ -z "${ALERT_URL:-}" && -n "${ALERTMANAGER_URL:-}" ]]; then
    export ALERT_URL="$ALERTMANAGER_URL"
  fi
  # Loki
  if [[ -z "${LOKI_URL:-}" && -n "${LOKI_ENDPOINT:-}" ]]; then
    export LOKI_URL="$LOKI_ENDPOINT"
  fi
  # Node Exporter textfile dir alias
  if [[ -z "${NODE_EXPORTER_TEXTFILE_DIR:-}" && -n "${TEXTFILE_COLLECTOR_DIR:-}" ]]; then
    export NODE_EXPORTER_TEXTFILE_DIR="$TEXTFILE_COLLECTOR_DIR"
  fi
}
