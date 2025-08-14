#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Prometheus Targets Gating Utility (non-destructive by default)

Description:
  Creates a gated copy of collections/prometheus/prometheus.yml with specified
  jobs removed (e.g., blackbox, blackbox-icmp, snmp). Writes to output/
  with a timestamp. Use --apply to replace the active file with a backup.

Usage:
  scripts/ops/targets_gating.sh [--jobs job1,job2,...] [--apply]

Examples:
  # Dry-run: remove noisy jobs and create a gated copy
  scripts/ops/targets_gating.sh --jobs blackbox,blackbox-icmp,snmp

  # Apply the gated config (backs up original)
  scripts/ops/targets_gating.sh --jobs blackbox,blackbox-icmp,snmp --apply
USAGE
}

apply=false
jobs=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) apply=true; shift ;;
    --jobs) jobs="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

src="collections/prometheus/prometheus.yml"
outdir="output"
mkdir -p "$outdir"
ts=$(date +%Y%m%d_%H%M%S)
out="$outdir/prometheus_gated_${ts}.yml"

if [[ ! -f "$src" ]]; then
  echo "Source Prometheus config not found: $src" >&2
  exit 1
fi

tmp=$(mktemp)
cp "$src" "$tmp"

IFS=',' read -r -a jarr <<< "$jobs"
if [[ -n "$jobs" ]]; then
  for j in "${jarr[@]}"; do
    # Remove job blocks that start with "- job_name: 'name'" up to the next blank line at same indentation
    # This is a heuristic; manual review recommended.
    awk -v JOB="$j" '
      BEGIN{skip=0}
      /^\s*-\s*job_name:\s*\047?"?"?([^\047\"]+)\047?"?"?/ {
        name=$0; gsub(/.*job_name:[[:space:]]*[\047\"]?/,"",name); gsub(/[\047\"].*$/,"",name);
        if (name==JOB) {skip=1}
      }
      skip && NF==0 {skip=0; next}
      !skip {print}
    ' "$tmp" > "$tmp.filtered" && mv "$tmp.filtered" "$tmp"
  done
fi

mv "$tmp" "$out"
echo "Wrote gated config: $out"

if $apply; then
  bkp="${src}.bak_${ts}"
  cp -f "$src" "$bkp"
  cp -f "$out" "$src"
  echo "Applied gated config to $src (backup: $(basename "$bkp"))"
fi
