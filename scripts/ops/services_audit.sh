#!/usr/bin/env bash
set -euo pipefail

# Service and data flow audit
# - Lists compose services
# - Checks key endpoints (Grafana, Prometheus, Alertmanager, InfluxDB)
# - Summarizes Prometheus targets, Grafana datasources, Loki/Promtail presence
# - Notes Resurgent connectivity variables

DOCKER_BIN=${DOCKER:-docker}
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env || true
  set +a
fi
OUT_DIR="output"
timestamp=$(date +%Y%m%d_%H%M%S)
report="$OUT_DIR/services_audit_${timestamp}.md"

mkdir -p "$OUT_DIR"

section() { echo -e "\n## $1\n" | tee -a "$report"; }
line() { echo "$*" | tee -a "$report"; }

echo "# Services Audit ($timestamp)" | tee "$report"

section "Compose Services"
compose_args=( -f base.yml )
if [ -f prod.yml ]; then compose_args+=( -f prod.yml ); fi
if $DOCKER_BIN compose "${compose_args[@]}" config --services >/dev/null 2>&1; then
  services=$($DOCKER_BIN compose "${compose_args[@]}" config --services || true)
  extra_services=""
  if [ -f docker-compose.yml ]; then
    extra_services=$($DOCKER_BIN compose -f docker-compose.yml config --services || true)
  fi
  all_services=$(printf "%s\n%s\n" "$services" "$extra_services" | awk 'NF' | sort -u)
  count=$(echo "$all_services" | awk 'NF' | wc -l | awk '{print $1}')
  line "Count: $count"
  echo "$all_services" | sed 's/^/- /' | tee -a "$report" >/dev/null
else
  line "docker compose not available or compose file invalid."
fi

section "Endpoints"
check_url() {
  local name="$1" url="$2"
  if curl -fsS -m 4 "$url" >/dev/null; then
    line "- ${name}: OK ($url)"
  else
    line "- ${name}: UNREACHABLE ($url)"
  fi
}
check_url Grafana        "http://localhost:3000/api/health"
check_url Prometheus     "http://localhost:9090/-/ready"
check_url Alertmanager   "http://localhost:9093/-/ready"
check_url InfluxDB       "http://localhost:8086/ping"

section "Prometheus Target Health"
if curl -fsS -m 4 "http://localhost:9090/api/v1/targets" -o /tmp/prom_targets.json 2>/dev/null; then
  python3 - "$report" <<'PY'
import sys, json
rep = sys.argv[1]
data = json.load(open('/tmp/prom_targets.json'))
active = data.get('data', {}).get('activeTargets', [])
total = len(active)
up = sum(1 for t in active if t.get('health') == 'up')
down = sum(1 for t in active if t.get('health') == 'down')
with open(rep, 'a') as f:
    f.write("\n- Targets total: %d (up: %d, down: %d)\n" % (total, up, down))
    if down:
        names = ["%s:%s" % (t.get('labels', {}).get('job','?'), t.get('discoveredLabels', {}).get('__address__','?')) for t in active if t.get('health')=='down']
        f.write("- Down examples: %s\n" % (", ".join(names[:5]) or 'n/a'))
PY
else
  line "- Unable to query Prometheus target API"
fi

section "Prometheus Query Probe"
if curl -fsS -m 4 "http://localhost:9090/api/v1/query?query=up" -o /tmp/prom_up.json 2>/dev/null; then
  python3 - "$report" <<'PY'
import sys, json, time
rep = sys.argv[1]
data = json.load(open('/tmp/prom_up.json'))
res = data.get('data', {}).get('result', [])
now = time.time()
fresh = 0
for r in res:
    try:
        ts = float(r['value'][0])
        if now - ts < 600:
            fresh += 1
    except Exception:
        pass
with open(rep, 'a') as f:
    f.write(f"- up series: {len(res)} (fresh <10m: {fresh})\n")
PY
else
  line "- Unable to query Prometheus 'up' metric"
fi

section "InfluxDB Probe"
if [ "${INFLUXDB_HTTP_AUTH_ENABLED:-}" = "true" ] || [ -n "${INFLUXDB_ADMIN_USER:-}" ]; then
  if [ -n "${INFLUXDB_ADMIN_USER:-}" ] && [ -n "${INFLUXDB_ADMIN_PASSWORD:-}" ]; then
    if curl -fsS -m 5 "http://localhost:8086/query" --data-urlencode "q=SHOW DATABASES" -u "${INFLUXDB_ADMIN_USER}:${INFLUXDB_ADMIN_PASSWORD}" -o /tmp/influx_dbs.json 2>/dev/null; then
      line "- InfluxDB databases listed (auth)"
    else
      line "- InfluxDB auth probe failed"
    fi
  else
    line "- InfluxDB auth enabled but creds not set in env"
  fi
else
  if curl -fsS -m 5 "http://localhost:8086/query" --data-urlencode "q=SHOW DATABASES" -o /tmp/influx_dbs.json 2>/dev/null; then
    line "- InfluxDB databases listed (no auth)"
  else
    line "- InfluxDB probe failed"
  fi
fi

section "Prometheus Targets"
if [ -d collections/prometheus/targets ]; then
  cnt=$(find collections/prometheus/targets -type f \( -name '*.yml' -o -name '*.yaml' -o -name '*.json' \) | wc -l | awk '{print $1}')
  line "Files: $cnt under collections/prometheus/targets"
  find collections/prometheus/targets -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' -o -name '*.json' \) -printf "- %f\n" | sort | tee -a "$report" >/dev/null
else
  line "No targets directory found."
fi

section "Prometheus Rules"
PROM_URL=${PROM_URL:-http://localhost:9090}
rule_dir="collections/prometheus"
files=$(find "$rule_dir" -maxdepth 1 -type f -name "*rules*.yml" -o -name "*rules*.yaml" 2>/dev/null | wc -l | awk '{print $1}')
line "- Rule files present: ${files} in $rule_dir"
if curl -fsS -m 4 "$PROM_URL/-/ready" >/dev/null 2>&1; then
  if curl -fsS -m 6 "$PROM_URL/api/v1/rules" -o /tmp/prom_rules.json 2>/dev/null; then
    python3 - "$report" <<'PY'
import json,sys
rep=sys.argv[1]
data=json.load(open('/tmp/prom_rules.json'))
groups=data.get('data',{}).get('groups',[])
rc=0
f=open(rep,'a')
f.write("- Rule groups loaded: %d\n"%len(groups))
f.close()
PY
  else
    line "- Unable to query Prometheus rules API"
  fi
else
  line "- Prometheus not reachable for rules query"
fi

section "Grafana Datasources"
if [ -d collections/grafana/provisioning/datasources ]; then
  find collections/grafana/provisioning/datasources -maxdepth 1 -type f -printf "- %f\n" | sort | tee -a "$report" >/dev/null
else
  line "No datasources directory found."
fi

section "Grafana Probe"
if curl -fsS -m 4 "http://localhost:3000/api/health" -o /tmp/gf_health.json 2>/dev/null; then
  line "- Grafana health reachable"
  if [ -n "${GRAFANA_USERNAME:-}" ] && [ -n "${GRAFANA_PASSWORD:-}" ]; then
    if curl -fsS -m 5 -u "${GRAFANA_USERNAME}:${GRAFANA_PASSWORD}" "http://localhost:3000/api/datasources" -o /tmp/gf_ds.json 2>/dev/null; then
      ds_count=$(python3 - <<'PY'
import json,sys
try:
  data=json.load(open('/tmp/gf_ds.json'))
  print(len(data))
except Exception:
  print('0')
PY
)
      line "- Grafana datasources API OK (count: ${ds_count})"
    else
      line "- Grafana datasources probe failed (auth?)"
    fi
  else
    line "- Grafana creds not set; skipping datasources API"
  fi
else
  line "- Grafana health API not reachable"
fi

section "Loki / Promtail"
[ -f collections/loki/loki-config.yml ] && line "- Loki config file: collections/loki/loki-config.yml" || true
[ -f collections/loki/local-config.yaml ] && line "- Loki local-config: collections/loki/local-config.yaml" || true
[ ! -f collections/loki/loki-config.yml ] && [ ! -f collections/loki/local-config.yaml ] && line "- Loki config: missing" || true
[ -d collections/promtail ] && line "- Promtail configs present (collections/promtail)" || line "- Promtail configs: missing"

section "Resurgent Connectivity"
_read_env_val() {
  local key="$1"; [ -f .env ] || return 0; sed -n -E "s/^${key}=([^#]*).*/\1/p" .env | tail -n1 | tr -d '\r' | xargs echo -n
}
RESURGENT_IP_VAL=${RESURGENT_IP:-$(_read_env_val RESURGENT_IP)}
RESURGENT_HOST_VAL=${RESURGENT_HOST:-$(_read_env_val RESURGENT_HOST)}
line "- RESURGENT_HOST=${RESURGENT_HOST_VAL:-unset}"
line "- RESURGENT_IP=${RESURGENT_IP_VAL:-unset}"
if [ -n "${RESURGENT_IP_VAL:-}" ]; then
  if curl -fsS -m 3 "http://${RESURGENT_IP_VAL}:9100/metrics" >/dev/null 2>&1; then
    line "- Node exporter reachable at ${RESURGENT_IP_VAL}:9100"
  else
    line "- Node exporter not reachable at ${RESURGENT_IP_VAL}:9100"
  fi
  if curl -fsS -m 3 "http://${RESURGENT_IP_VAL}:8081/metrics" >/dev/null 2>&1; then
    line "- cAdvisor reachable at ${RESURGENT_IP_VAL}:8081"
  else
    line "- cAdvisor not reachable at ${RESURGENT_IP_VAL}:8081"
  fi
fi

echo "\nReport: $report"
