#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
UFW Allowlist Runbook (dry-run by default)

Description:
  Generates UFW rules to allow access to published service ports only from
  specified CIDR subnets. By default, prints the commands (dry-run).

Usage:
  scripts/ops/ufw_allowlist_runbook.sh [--apply] [--subnets CIDR[,CIDR...]] [--ports PORT[,PORT...]]

Options:
  --apply                 Apply rules (disables dry-run); otherwise echo only
  --subnets CIDRS         Comma-separated CIDR list (default: 192.168.1.0/24,192.168.50.0/24,192.168.30.0/24)
  --ports PORTS           Comma-separated ports (default: 3000,9090,9093,8086,3100,9100,9104,9115,9116)

Examples:
  # Dry-run, default subnets and ports
  scripts/ops/ufw_allowlist_runbook.sh

  # Apply with custom subnets and ports
  scripts/ops/ufw_allowlist_runbook.sh --apply \
    --subnets 192.168.1.0/24,192.168.50.0/24,192.168.30.0/24 \
    --ports 3000,9090,9093,8086,3100,9100,9104,9115,9116

Notes:
  - This script does not enable UFW automatically. If UFW is inactive,
    it will print the enable command as part of the plan in dry-run mode.
  - Review the printed plan before applying on a host.
USAGE
}

apply=false
subnets="192.168.1.0/24,192.168.50.0/24,192.168.30.0/24"
ports="3000,9090,9093,8086,3100,9100,9104,9115,9116"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      apply=true; shift ;;
    --subnets)
      subnets="${2:-}"; shift 2 ;;
    --ports)
      ports="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

IFS=',' read -r -a subnet_arr <<< "$subnets"
IFS=',' read -r -a port_arr <<< "$ports"

ufw_bin=$(command -v ufw || true)
timestamp=$(date +%Y%m%d_%H%M%S)

echo ":: UFW Allowlist Plan ($timestamp) ::"
echo "Apply: $apply"
echo "Subnets: ${subnet_arr[*]}"
echo "Ports: ${port_arr[*]}"

run() {
  if $apply; then
    echo "+ $*"; eval "$@"
  else
    echo "[DRY-RUN] $*"
  fi
}

if [[ -z "$ufw_bin" ]]; then
  echo "ufw not found in PATH. Install UFW first." >&2
  exit 1
fi

# Show UFW status
run "$ufw_bin status verbose"

# Default deny incoming to tighten surface (idempotent)
run "$ufw_bin default deny incoming"
run "$ufw_bin default allow outgoing"

# Allow from each subnet to each port
for cidr in "${subnet_arr[@]}"; do
  for port in "${port_arr[@]}"; do
    run "$ufw_bin allow from $cidr to any port $port proto tcp"
  done
done

# Optionally enable UFW (printed even in dry-run)
run "$ufw_bin enable"

echo ":: Plan complete. Review above commands before applying on a host. ::"
