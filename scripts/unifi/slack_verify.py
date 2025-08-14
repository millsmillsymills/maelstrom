#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Dict, Optional

import requests


def auth_test(token: str) -> Dict[str, Any]:
    r = requests.post(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return r.json()


def conversations_list(token: str, cursor: Optional[str] = None) -> Dict[str, Any]:
    params = {"types": "public_channel,private_channel", "limit": 500}
    if cursor:
        params["cursor"] = cursor
    r = requests.get(
        "https://slack.com/api/conversations.list",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=20,
    )
    return r.json()


def conversations_info(token: str, channel: str) -> Dict[str, Any]:
    r = requests.get(
        "https://slack.com/api/conversations.info",
        headers={"Authorization": f"Bearer {token}"},
        params={"channel": channel},
        timeout=10,
    )
    return r.json()


def resolve_channel_id(token: str, channel: str) -> Dict[str, Any]:
    # If already an ID-like string, validate access
    if re.match(r"^[CGD][A-Z0-9]+$", channel):
        info = conversations_info(token, channel)
        return {
            "input": channel,
            "channel_id": channel if info.get("ok") else None,
            "info": info,
        }
    # Strip leading # if any
    name = channel.lstrip("#")
    cursor = None
    while True:
        data = conversations_list(token, cursor)
        if not data.get("ok"):
            return {"input": channel, "channel_id": None, "error": data}
        for ch in data.get("channels", []):
            if ch.get("name") == name:
                return {"input": channel, "channel_id": ch.get("id"), "channel": ch}
        cursor = (data.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    return {"input": channel, "channel_id": None, "error": {"reason": "not_found"}}


def run() -> int:
    ap = argparse.ArgumentParser(
        description="Verify Slack bot token and resolve channel ID"
    )
    ap.add_argument("--token", default=os.environ.get("SLACK_BOT_TOKEN", ""))
    ap.add_argument("--channel", default=os.environ.get("SLACK_CHANNEL", ""))
    args = ap.parse_args()

    out: Dict[str, Any] = {"ok": True}
    if not args.token:
        out.update({"ok": False, "error": "missing_token"})
        print(json.dumps(out, indent=2))
        return 0

    at = auth_test(args.token)
    out["auth_test"] = at
    if not at.get("ok"):
        out["ok"] = False

    if args.channel:
        ch = resolve_channel_id(args.token, args.channel)
        out["channel"] = ch
        if not ch.get("channel_id"):
            out["ok"] = False

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
