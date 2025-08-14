#!/usr/bin/env bash
set -euo pipefail
source /usr/local/lib/codex_env.sh 2>/dev/null || true

COMPOSE_FILES=( -f base.yml -f docker-compose.secrets.yml )

have() { command -v "$1" >/dev/null 2>&1; }

http_code() {
  local url="$1"; shift || true
  if have curl; then
    curl -k -sSL -o /dev/null -w "%{http_code}" "$url" || echo 000
  elif have wget; then
    wget -q --server-response --spider "$url" 2>&1 | awk '/^  HTTP/{code=$2} END{print code+0}'
  else
    echo 000
  fi
}

check_http_retry() {
  # name service url ok_codes [max_attempts] [initial_delay]
  local name="$1" service="$2" url="$3" ok_codes="$4" attempts="${5:-10}" delay="${6:-3}"
  local i=1 code
  while (( i <= attempts )); do
    code=$(http_code "$url")
    if [[ " $ok_codes " == *" $code "* ]]; then
      printf "[OK]   %-18s %s (code %s)\n" "$name" "$url" "$code"
      return 0
    fi
    printf "[wait] %-18s %s (code %s) attempt %d/%d\n" "$name" "$url" "$code" "$i" "$attempts"
    sleep "$delay"
    if (( delay < 15 )); then delay=$((delay+2)); fi
    i=$((i+1))
  done
  printf "[FAIL] %-18s %s (last code %s, expect %s)\n" "$name" "$url" "$code" "$ok_codes"
  if have ${DOCKER} && [ -n "$service" ]; then
    echo "--- Logs: $service (last 80 lines) ---"
    ${DOCKER} compose "${COMPOSE_FILES[@]}" logs --no-color --tail 80 "$service" || true
    echo "--- End logs: $service ---"
  fi
  return 1
}

echo "== Docker services (ps) =="
if have docker; then
  ${DOCKER} compose "${COMPOSE_FILES[@]}" ps || true
else
  echo "${DOCKER} not available in PATH"
fi

echo
echo "== HTTP health checks =="
fail=0

check_http_retry influxdb influxdb         http://127.0.0.1:8086/ping "200 204" 15 2 || fail=$((fail+1))
check_http_retry grafana grafana           http://127.0.0.1:3000/api/health "200" 20 2 || fail=$((fail+1))
check_http_retry prometheus prometheus     http://127.0.0.1:9090/-/ready "200" 20 2 || fail=$((fail+1))
check_http_retry alertmanager alertmanager http://127.0.0.1:9093/-/ready "200" 20 2 || fail=$((fail+1))
check_http_retry loki loki                 http://127.0.0.1:3100/ready "200" 20 2 || fail=$((fail+1))
check_http_retry cadvisor cadvisor         http://127.0.0.1:8081/ "200 302 301" 15 2 || fail=$((fail+1))
check_http_retry node-exporter node-exporter http://127.0.0.1:9100/metrics "200" 15 2 || fail=$((fail+1))
check_http_retry mysql-exporter mysql-exporter http://127.0.0.1:9104/metrics "200" 15 2 || fail=$((fail+1))
check_http_retry blackbox-exporter blackbox-exporter http://127.0.0.1:9115/metrics "200" 15 2 || fail=$((fail+1))
check_http_retry snmp-exporter snmp-exporter http://127.0.0.1:9116/metrics "200" 15 2 || fail=$((fail+1))
check_http_retry telegraf telegraf         http://127.0.0.1:9273/metrics "200" 15 2 || fail=$((fail+1))

code=$(http_code http://127.0.0.1:8080/)
if [[ "$code" =~ ^3|2 ]]; then
  printf "[OK]   %-18s %s (code %s)\n" "zabbix-web" "http://127.0.0.1:8080/" "$code"
else
  printf "[FAIL] %-18s %s (code %s, expect 200-399)\n" "zabbix-web" "http://127.0.0.1:8080/" "$code"
  if have docker; then
    echo "--- Logs: zabbix-web (last 80 lines) ---"
    ${DOCKER} compose "${COMPOSE_FILES[@]}" logs --no-color --tail 80 zabbix-web || true
    echo "--- End logs: zabbix-web ---"
  fi
  fail=$((fail+1))
fi

echo
if (( fail == 0 )); then
  echo "All checks passed."
  exit 0
else
  echo "$fail check(s) failed. Inspect logs with: ${DOCKER} compose ${COMPOSE_FILES[*]} logs <service>"
  exit 1
fi
