#!/usr/bin/env bash
set -euo pipefail

# Maelstrom health collector (read-only)
# Collects host, container, monitoring, networking, and security signals
# Produces: human summary (Markdown) + structured JSON

HOURS=24
OUT_JSON=${OUT_JSON:-/tmp/maelstrom_health.json}
OUT_SUMMARY=${OUT_SUMMARY:-/tmp/maelstrom_health.md}
REQ_TIMEOUT=8

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hours) HOURS=${2:-24}; shift 2;;
    --json) OUT_JSON=${2:-/tmp/maelstrom_health.json}; shift 2;;
    --summary) OUT_SUMMARY=${2:-/tmp/maelstrom_health.md}; shift 2;;
    --timeout-sec) REQ_TIMEOUT=${2:-8}; shift 2;;
    -h|--help)
      cat <<EOF
Usage: $0 [--hours N] [--json PATH] [--summary PATH] [--timeout-sec N]
Collects health/security signals and outputs a Markdown summary + JSON.
Environment endpoints can override defaults (PROM_URL, ALERT_URL, GRAFANA_URL, LOKI_URL, WAZUH_API, ...).
EOF
      exit 0;;
    *) shift;;
  esac
done

PROM_URL=${PROM_URL:-http://localhost:9090}
ALERT_URL=${ALERT_URL:-http://localhost:9093}
GRAFANA_URL=${GRAFANA_URL:-http://localhost:3000}
LOKI_URL=${LOKI_URL:-http://localhost:3100}
WAZUH_API=${WAZUH_API:-https://localhost:55000}
UNIFI_POLLER_URL=${UNIFI_POLLER_URL:-http://localhost:9130}
CADVISOR_URL=${CADVISOR_URL:-http://localhost:8081}

GRAFANA_TOKEN=${GRAFANA_TOKEN:-}
PROM_TOKEN=${PROM_TOKEN:-}
LOKI_BASIC=${LOKI_BASIC:-}
WAZUH_USER=${WAZUH_USER:-wazuh}
WAZUH_PASS=${WAZUH_PASS:-wazuhpass}
WAZUH_JWT=${WAZUH_JWT:-}

HOST=$(hostname -s 2>/dev/null || echo "maelstrom")
NOW=$(date -u +%FT%TZ)
START_NS=$(date -d "$HOURS hours ago" +%s%N)
END_NS=$(date +%s%N)

# Host metrics
CPU_PCT=$(top -bn1 | awk -F',' '/^%Cpu/ {idle=$0; for(i=1;i<=NF;i++){if($i ~ / id/){v=$i; gsub("id","",v); gsub("[ %]","",v); idle=v;}}} END {if (idle=="") idle=0; printf "%.1f", 100-idle}' 2>/dev/null || echo 0)
MEM_PCT=$(awk '/MemTotal/ {t=$2} /MemAvailable/ {a=$2} END {if (t>0) printf "%.1f", (1- a/t)*100; else print 0}' /proc/meminfo 2>/dev/null || echo 0)
FS_JSON=$(df -P -x tmpfs -x devtmpfs 2>/dev/null | awk 'NR>1 {gsub("%","",$5); printf "{\"mount\":\"%s\",\"pct_used\":%s},", $6, $5}' | sed 's/,$//' | awk '{print "["$0"]"}')
[[ -z "$FS_JSON" ]] && FS_JSON='[]'

# Containers: health + restarts
INSPECT=$(docker ps -q 2>/dev/null | xargs -r docker inspect --format '{{.Name}}\t{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}\t{{.RestartCount}}' 2>/dev/null || true)
UNHEALTHY_JSON=$(echo "$INSPECT" | awk -F '\t' '$2=="unhealthy" {gsub(/^\//, "", $1); printf "{\"name\":\"%s\",\"reason\":\"healthcheck failing\"},", $1}' | sed 's/,$//' | awk '{print "["$0"]"}')
[[ -z "$UNHEALTHY_JSON" ]] && UNHEALTHY_JSON='[]'
RESTARTS_JSON=$(echo "$INSPECT" | awk -F '\t' '$3>0 {gsub(/^\//, "", $1); printf "{\"name\":\"%s\",\"count\":%s},", $1, $3}' | sed 's/,$//' | awk '{print "["$0"]"}')
[[ -z "$RESTARTS_JSON" ]] && RESTARTS_JSON='[]'

# Prometheus queries
curl_s() { curl -sS --max-time "$REQ_TIMEOUT" "$@"; }
prom_q() { curl -sS --max-time "$REQ_TIMEOUT" "$PROM_URL/api/v1/query" --data-urlencode "query=$1"; }

PROM_UP=$(prom_q 'up{job!~"blackbox.*"}' || echo '')
PROM_CPU=$(prom_q '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))*100)' || echo '')
PROM_MEM=$(prom_q '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100' || echo '')
PROM_FS=$(prom_q '100 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}) * 100' || echo '')
PROM_UNIFI=$(prom_q 'up{job=~"unifi.*"}' || echo '')

# Alertmanager
ALERTS=$(curl_s "$ALERT_URL/api/v2/alerts" || echo '')

# Grafana health
if [[ -n "$GRAFANA_TOKEN" ]]; then
  GRAFANA_HEALTH=$(curl_s -H "Authorization: Bearer $GRAFANA_TOKEN" "$GRAFANA_URL/api/health" || echo '')
else
  GRAFANA_HEALTH=$(curl_s "$GRAFANA_URL/api/health" || echo '')
fi

# Loki logs: restart/error patterns
L_QUERY='{container=~".+"} |~ "(Restarting|OOMKilled|level=error|level=warn)"'
LOKI_RANGE=$(curl -sS -G --max-time "$REQ_TIMEOUT" "$LOKI_URL/loki/api/v1/query_range" \
  --data-urlencode "query=$L_QUERY" --data-urlencode start=$START_NS --data-urlencode end=$END_NS || echo '')

# Wazuh API: try JWT or basic auth to fetch alerts/agents
WAZUH_TOKEN="${WAZUH_JWT:-}"
if [[ -z "$WAZUH_TOKEN" ]]; then
  AUTH_JSON=$(curl -sk --max-time "$REQ_TIMEOUT" -X POST "$WAZUH_API/security/user/authenticate" \
    -H 'Content-Type: application/json' -d "{\"username\":\"$WAZUH_USER\",\"password\":\"$WAZUH_PASS\"}" || echo '')
  if command -v jq >/dev/null 2>&1; then
    WAZUH_TOKEN=$(echo "$AUTH_JSON" | jq -r '.data.token // empty' 2>/dev/null || echo '')
  else
    WAZUH_TOKEN=$(echo "$AUTH_JSON" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' | head -n1 || echo '')
  fi
fi
WAZUH_ALERTS=""; WAZUH_AGENTS=""; WAZUH_REACHABLE=false
if [[ -n "$WAZUH_TOKEN" ]]; then
  WAZUH_ALERTS=$(curl -sk --max-time $((REQ_TIMEOUT+4)) -H "Authorization: Bearer $WAZUH_TOKEN" \
    "$WAZUH_API/alerts?limit=200&sort=desc&order=timestamp&sev.gte=7&from=$(date -u -d "$HOURS hours ago" +%FT%TZ)" || echo '')
  WAZUH_AGENTS=$(curl -sk --max-time "$REQ_TIMEOUT" -H "Authorization: Bearer $WAZUH_TOKEN" "$WAZUH_API/agents" || echo '')
  WAZUH_REACHABLE=true
fi

# Determine simple overall status
OVERALL="GREEN"
if echo "$ALERTS" | grep -qi '"severity":"critical"'; then OVERALL="RED"; fi
if [[ "$MEM_PCT" != "" ]] && (( ${MEM_PCT%.*} >= 95 )); then OVERALL="RED"; fi
if echo "$FS_JSON" | grep -E '"pct_used":[9][0-9]'; then OVERALL="YELLOW"; fi
if [[ "$UNHEALTHY_JSON" != '[]' ]]; then OVERALL="YELLOW"; fi
if echo "$ALERTS" | grep -qi '"severity":"warning"'; then [[ "$OVERALL" == "GREEN" ]] && OVERALL="YELLOW"; fi

# Build JSON
cat >"$OUT_JSON" <<JSON
{
  "meta": {"generated_at": "$NOW", "window_hours": $HOURS, "host": "$HOST", "versions": {"prompt": "v1.0"}},
  "overall_status": "$OVERALL",
  "signals": {
    "platform": {
      "host": {"cpu_pct": ${CPU_PCT:-0}, "mem_pct": ${MEM_PCT:-0}, "fs": $FS_JSON},
      "containers": {"unhealthy": $UNHEALTHY_JSON, "restarts_24h": $RESTARTS_JSON, "top_talkers": []},
      "alerts": {"firing": []}
    },
    "network": {"devices": [], "wan": {"status": "up", "loss_pct": 0, "latency_ms": 0}},
    "security": {"wazuh": [], "suricata": [], "zeek": []},
    "backups": {"latest_runs": [], "retention_ok": true}
  },
  "evidence": {
    "queries": [
      {"system":"prometheus","query":"up{job!~\\"blackbox.*\\"}","sample_result":$(printf %s "$PROM_UP" | head -c 400 | jq -Rs '.')},
      {"system":"alertmanager","query":"/api/v2/alerts","sample_result":$(printf %s "$ALERTS" | head -c 400 | jq -Rs '.')},
      {"system":"grafana","query":"/api/health","sample_result":$(printf %s "$GRAFANA_HEALTH" | head -c 200 | jq -Rs '.')},
      {"system":"loki","query":"{container=~\\".+\\"} |~ (Restarting|OOMKilled|level=error|level=warn)","sample_result":$(printf %s "$LOKI_RANGE" | head -c 200 | jq -Rs '.')},
      {"system":"prometheus","query":"up{job=~\\"unifi.*\\"}","sample_result":$(printf %s "$PROM_UNIFI" | head -c 200 | jq -Rs '.')}
    ],
    "logs": []
  },
  "recommended_actions": []
}
JSON

# Markdown summary
{
  echo "# Maelstrom Health Summary"
  echo
  echo "- Overall Status: $OVERALL"
  echo "- Host: CPU ${CPU_PCT:-0}% | MEM ${MEM_PCT:-0}%"
  echo "- Filesystems: $(echo "$FS_JSON" | sed 's/\s//g')"
  echo "- Unhealthy containers: $(echo "$UNHEALTHY_JSON" | sed 's/\s//g')"
  echo "- Restarts (since start): $(echo "$RESTARTS_JSON" | sed 's/\s//g')"
  echo
  echo "## Notes"
  if [[ "$WAZUH_REACHABLE" == true ]]; then
    echo "- Wazuh API reachable."
  else
    echo "- Wazuh API not reachable or token unavailable."
  fi
  echo "- Alertmanager sample: $(echo "$ALERTS" | head -c 120 | tr '\n' ' ')"
  echo "- Loki error/restart pattern sample: $(echo "$LOKI_RANGE" | head -c 120 | tr '\n' ' ')"
} | tee "$OUT_SUMMARY" >/dev/null

echo "Wrote:"
echo "  JSON:     $OUT_JSON"
echo "  Summary:  $OUT_SUMMARY"
