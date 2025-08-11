#!/usr/bin/env bash
# Comprehensive systems health check for Maelstrom/Resurgent
set -euo pipefail
source /usr/local/lib/codex_env.sh 2>/dev/null || true

log() { printf "%s %s\n" "[$(date -Is)]" "$*"; }

# Determine host role
HOSTNAME=$(hostname)
OS_NAME=$(grep -E '^NAME=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "unknown")
ROLE="unknown"
if [ -f /etc/unraid-version ] || [ -d /boot/config ]; then ROLE="resurgent"; fi
if echo "$HOSTNAME" | grep -qi maelstrom; then ROLE="maelstrom"; fi

# Prepare report directory
STAMP=$(date +%Y%m%dT%H%M%S)
DEFAULT_DIR=/var/lib/system_health
REPORT_DIR=$DEFAULT_DIR
if ! mkdir -p "$REPORT_DIR" 2>/dev/null; then
  REPORT_DIR="$HOME/system_health"
  mkdir -p "$REPORT_DIR"
fi
MD="$REPORT_DIR/healthcheck-${HOSTNAME}-${STAMP}.md"
JSON="$REPORT_DIR/healthcheck-${HOSTNAME}-${STAMP}.json"

ISSUES=() # human-readable issue strings
JSON_ISSUES=() # JSON fragments

add_issue() { ISSUES+=("$1"); JSON_ISSUES+=("{\"summary\":$(printf %q "$1" | sed 's/^/"/; s/$/"/'),\"category\":\"$2\"}"); }

# Helper: command runner that won't fail script
try() { "$@" 2>&1 || true; }

# General system
UPTIME=$(try uptime)
LOADAVG=$(cut -d' ' -f1-3 /proc/loadavg)
NPROC=$(nproc)
MEM=$(try free -h)
SWAP=$(try swapon --show)
DISK=$(try df -hT)
LSBLK=$(try lsblk -o NAME,TYPE,SIZE,MOUNTPOINT)

# Docker status
DOCKER_BIN=$(command -v ${DOCKER} || true)
if [ -n "$DOCKER_BIN" ]; then
  DOCKER_PS=$(try ${DOCKER} ps --format '{{.Names}}\t{{.Status}}\t{{.Image}}')
else
  DOCKER_PS="${DOCKER} not available"
fi

# Network
IPADDR=$(try ip -br addr)
ROUTE=$(try ip route show default)
RESOLV=$(grep -E '^(nameserver|search)' /etc/resolv.conf 2>/dev/null | tr '\n' ' ' || true)

# Listening ports
PORTS=$(try ss -ltn)

# Quick heuristics for resource pressure
used_mem_pct=$(free | awk '/Mem:/ {printf("%.0f", $3/$2*100)}')
if [ "${used_mem_pct:-0}" -gt 90 ]; then add_issue "High memory usage: ${used_mem_pct}%" resource; fi

read1=$(echo "$LOADAVG" | awk '{print $1*100}')
read1=${read1%.*}
threshold=$((NPROC*100))
if [ "${read1:-0}" -gt "$threshold" ]; then add_issue "High 1m loadavg vs cores: ${LOADAVG} on ${NPROC} cores" resource; fi

# Service presence (best-effort via ports)
want_ports=(9090 9093 3000 3100 9100 9104 9116)
for p in "${want_ports[@]}"; do
  if echo "$PORTS" | grep -q ":$p\b"; then :; else
    case "$p" in
      9090) add_issue "Prometheus port 9090 not listening" runtime ;;
      9093) add_issue "Alertmanager port 9093 not listening" runtime ;;
      3000) add_issue "Grafana port 3000 not listening" runtime ;;
      3100) add_issue "Loki port 3100 not listening" runtime ;;
      9100) add_issue "Node Exporter port 9100 not listening" runtime ;;
      9104) add_issue "MySQL Exporter port 9104 not listening" runtime ;;
      9116) add_issue "Blackbox Exporter port 9116 not listening" runtime ;;
    esac
  fi
done

# Attempt remediations (safe only)
restart_service() {
  local svc="$1"
  if sysctl_wrap is-enabled "$svc" >/dev/null 2>&1; then
    if ! sysctl_wrap is-active "$svc" >/dev/null 2>&1; then
      log "Restarting service: $svc"
      try sysctl_wrap restart "$svc" || true
    fi
  fi
}

for svc in prometheus grafana-server loki alertmanager node_exporter mysqld_exporter blackbox_exporter; do
  restart_service "$svc"
done

# Docker container remediation (only restart stuck ones)
if [ -n "$DOCKER_BIN" ]; then
  while IFS=$'\t' read -r name status image; do
    case "$status" in
      Exited*|Created*|Dead*|Restarting*)
        log "Restarting container $name ($status)"
        try ${DOCKER} restart "$name" >/dev/null || true
        add_issue "Restarted container $name ($status)" runtime
      ;;
    esac
  done < <(${DOCKER} ps -a --format '{{.Names}}\t{{.Status}}\t{{.Image}}')
fi

# Assemble reports
{
  echo "# System Health Report — $HOSTNAME"
  echo "- Role: $ROLE"
  echo "- OS: $OS_NAME"
  echo "- Generated: $(date -Is)"
  echo
  echo "## Summary"
  if [ ${#ISSUES[@]} -eq 0 ]; then
    echo "- No critical issues detected."
  else
    for i in "${ISSUES[@]}"; do echo "- $i"; done
  fi
  echo
  echo "## General"
  echo '```'
  echo "$UPTIME"
  echo "CPUs: $NPROC  Load: $LOADAVG"
  echo "$MEM"
  echo "$SWAP"
  echo '```'
  echo
  echo "## Disks"
  echo '```'
  echo "$DISK"
  echo "$LSBLK"
  echo '```'
  echo
  echo "## Network"
  echo '```'
  echo "$IPADDR"
  echo "$ROUTE"
  echo "resolv.conf: $RESOLV"
  echo '```'
  echo
  echo "## Services"
  echo '```'
  echo "$PORTS"
  echo
  echo "Docker:\n$DOCKER_PS"
  echo '```'
} > "$MD"

{
  echo '{'
  printf '  "host": "%s", "role": "%s", "os": "%s", "generated": "%s",\n' "$HOSTNAME" "$ROLE" "$OS_NAME" "$(date -Is)"
  printf '  "issues": [\n'
  if [ ${#JSON_ISSUES[@]} -gt 0 ]; then
    IFS=,$'\n'; echo "    ${JSON_ISSUES[*]}"; IFS=$' \t\n'
  fi
  echo '  ],'
  printf '  "cpu": {"cpus": %s, "loadavg": "%s"},\n' "$NPROC" "$LOADAVG"
  printf '  "memory": %s,\n' "$(free -b | awk 'NR==1{print "{\"header\":\""$0"\"}"} NR==2{print "{\"total\":"$2",\"used\":"$3",\"free\":"$4"}"}')"
  printf '  "disks": %s,\n' "$(df -P | awk 'NR>1{printf("{\"fs\":\"%s\",\"size\":\"%s\",\"used\":\"%s\",\"avail\":\"%s\",\"mount\":\"%s\"}%s",$1,$2,$3,$4,$6,(NR>1?",":""))}' | sed 's/}$/}],/;1s/^/[/' | sed 's/],$/]/')"
  printf '  "network": {"route": "%s", "resolv": "%s"},\n' "$(echo "$ROUTE" | sed 's/\\/\\\\/g')" "$(echo "$RESOLV" | sed 's/\\/\\\\/g')"
  printf '  "ports": %s,\n' "$(ss -ltn | tail -n +2 | awk '{print $4}' | awk -F: '{print $NF}' | sort -nu | awk 'BEGIN{printf("[")} {printf(n?",%s":"%s",$1,$1); n=1} END{print "]"}')"
  printf '  "docker_ps": %s\n' "$(if [ -n "$DOCKER_BIN" ]; then ${DOCKER} ps --format '{{json .}}' | paste -sd, - | sed 's/^/[/' | sed 's/$/]/'; else echo '[]'; fi)"
  echo '}'
} > "$JSON"

log "Report written: $MD"
log "Report written: $JSON"
echo "$MD"