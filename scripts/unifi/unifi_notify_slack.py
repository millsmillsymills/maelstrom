#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any, Dict

try:
    import requests
except Exception:
    requests = None  # We'll fall back to printing


def build_message(report: Dict[str, Any]) -> str:
    t = report.get("totals", {})
    top_ssids = report.get("top_ssids", [])[:3]
    top_clients = report.get("top_clients", [])[:3]

    lines = []
    lines.append("UniFi export pipeline completed (7d window)")
    if t:
        parts = [
            f"{k}:{t[k]}"
            for k in ("events", "alarms", "clients", "devices", "users", "wlan")
            if k in t
        ]
        if parts:
            lines.append("Totals: " + ", ".join(parts))
    if top_ssids:
        lines.append("Top SSIDs: " + ", ".join([f"{n} ({c})" for n, c in top_ssids]))
    if top_clients:
        lines.append(
            "Top Clients: " + ", ".join([f"{n} ({c})" for n, c in top_clients])
        )
    return "\n".join(lines)


def send_slack(webhook: str, text: str) -> bool:
    if not webhook:
        print("SLACK_WEBHOOK_URL not set; skipping notification", file=sys.stderr)
        return False
    if requests is None:
        print("requests not available; skipping Slack send", file=sys.stderr)
        return False
    try:
        resp = requests.post(webhook, json={"text": text}, timeout=10)
        if resp.status_code >= 200 and resp.status_code < 300:
            return True
        print(
            f"Slack webhook failed: HTTP {resp.status_code} {resp.text[:200]}",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"Slack send error: {e}", file=sys.stderr)
    return False


def run() -> int:
    ap = argparse.ArgumentParser(description="Send UniFi report summary to Slack")
    ap.add_argument("--report-json", required=True)
    ap.add_argument("--webhook", default=os.environ.get("SLACK_WEBHOOK_URL", ""))
    args = ap.parse_args()

    report = json.loads(pathlib.Path(args.report_json).read_text(encoding="utf-8"))
    msg = build_message(report)
    ok = send_slack(args.webhook, msg)
    print("Slack notification sent" if ok else "Slack notification skipped/failure")
    return 0 if ok else 0


if __name__ == "__main__":
    raise SystemExit(run())
