#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any, Dict, List
import time


def write_metrics(
    report: Dict[str, Any], out_path: pathlib.Path, window: str = "7d"
) -> None:
    lines: List[str] = []
    totals = report.get("totals", {})
    ts = int(time.time())

    lines.append("# TYPE unifi_export_run_timestamp_seconds gauge")
    lines.append(f"unifi_export_run_timestamp_seconds {ts}")

    lines.append("# TYPE unifi_export_total gauge")
    for res, val in totals.items():
        try:
            v = int(val)
        except Exception:
            continue
        lines.append(f'unifi_export_total{{resource="{res}",window="{window}"}} {v}')

    # Optional: top 3 SSIDs and clients counts
    for i, (ssid, cnt) in enumerate(report.get("top_ssids", [])[:3], start=1):
        lines.append(
            f'unifi_export_top_ssid_count{{rank="{i}",ssid="{ssid}",window="{window}"}} {int(cnt)}'
        )
    for i, (label, cnt) in enumerate(report.get("top_clients", [])[:3], start=1):
        lines.append(
            f'unifi_export_top_client_count{{rank="{i}",label="{label}",window="{window}"}} {int(cnt)}'
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> int:
    ap = argparse.ArgumentParser(
        description="Emit Prometheus metrics from UniFi report JSON"
    )
    ap.add_argument("--report-json", required=True, help="Path to report JSON")
    ap.add_argument("--out", required=True, help="Output metrics file path (.prom)")
    ap.add_argument("--window", default="7d")
    args = ap.parse_args()

    report = json.loads(pathlib.Path(args.report_json).read_text(encoding="utf-8"))
    out_path = pathlib.Path(args.out)
    write_metrics(report, out_path, window=args.window)
    print(f"Wrote metrics: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
