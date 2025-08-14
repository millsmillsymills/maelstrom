#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

try:
    import requests
except Exception:
    requests = None


def send_webhook(url: str, text: str) -> None:
    if not url or requests is None:
        return
    try:
        requests.post(url, json={"text": text}, timeout=10)
    except Exception:
        pass


def run() -> int:
    ap = argparse.ArgumentParser(
        description="Check last UniFi export status and alert if stale/empty"
    )
    ap.add_argument("--export-dir", default="output/unifi/last7d")
    ap.add_argument("--max-age-hours", type=int, default=12)
    ap.add_argument("--min-events", type=int, default=1)
    ap.add_argument("--webhook", default=os.environ.get("SLACK_WEBHOOK_URL", ""))
    args = ap.parse_args()

    export_dir = pathlib.Path(args.export_dir)
    summary_path = export_dir / "summary.json"
    ok = True
    msgs = []
    now = time.time()

    if not summary_path.exists():
        ok = False
        msgs.append(f"Missing summary.json in {export_dir}")
    else:
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as e:
            ok = False
            msgs.append(f"Invalid summary.json: {e}")
            data = []

        mtime = summary_path.stat().st_mtime
        age_h = (now - mtime) / 3600.0
        if age_h > args.max_age_hours:
            ok = False
            msgs.append(
                f"summary.json is stale: age={age_h:.1f}h > {args.max_age_hours}h"
            )

        # Validate counts
        counts = {
            item.get("resource"): int(item.get("count", 0))
            for item in data
            if isinstance(item, dict)
        }
        if counts.get("events", 0) < args.min_events:
            ok = False
            msgs.append(
                f"events below threshold: {counts.get('events', 0)} < {args.min_events}"
            )

    if ok:
        print("Status OK")
        return 0

    text = "UniFi export status check failed:\n- " + "\n- ".join(msgs)
    print(text, file=sys.stderr)
    send_webhook(args.webhook, text)
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
