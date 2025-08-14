#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import pathlib
import sys

try:
    import requests
except Exception:
    requests = None


def run() -> int:
    ap = argparse.ArgumentParser(
        description="Upload a file to Slack via files.upload API"
    )
    ap.add_argument("--token", default=os.environ.get("SLACK_BOT_TOKEN", ""))
    ap.add_argument(
        "--channels",
        default=os.environ.get("SLACK_CHANNEL", ""),
        help="Comma-separated channel IDs or names",
    )
    ap.add_argument("--file", required=True, help="Path to file to upload")
    ap.add_argument("--title", default="UniFi Report")
    ap.add_argument("--initial-comment", default="")
    args = ap.parse_args()

    if not args.token or not args.channels:
        print(
            "Missing SLACK_BOT_TOKEN or SLACK_CHANNEL; skipping upload", file=sys.stderr
        )
        return 0
    if requests is None:
        print("requests not available; cannot upload to Slack", file=sys.stderr)
        return 0

    fpath = pathlib.Path(args.file)
    if not fpath.exists():
        print(f"File not found: {fpath}", file=sys.stderr)
        return 2

    try:
        with fpath.open("rb") as fh:
            resp = requests.post(
                "https://slack.com/api/files.upload",
                headers={"Authorization": f"Bearer {args.token}"},
                data={
                    "channels": args.channels,
                    "title": args.title,
                    "initial_comment": args.initial_comment,
                },
                files={"file": (fpath.name, fh, "text/markdown")},
                timeout=30,
            )
        data = resp.json()
        if not data.get("ok"):
            print(f"Slack upload failed: {data}", file=sys.stderr)
            return 1
        print("Slack file upload successful")
        return 0
    except Exception as e:
        print(f"Slack upload error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
