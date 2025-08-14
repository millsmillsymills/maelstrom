#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sqlite3
from typing import Any, Dict, List, Tuple


def load_table(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    rows = cur.execute(f"SELECT data FROM {table}").fetchall()
    out: List[Dict[str, Any]] = []
    for (d,) in rows:
        try:
            out.append(json.loads(d))
        except Exception:
            pass
    return out


def top_k(counter: collections.Counter, k: int) -> List[Tuple[str, int]]:
    return counter.most_common(k)


def summarize(db_path: pathlib.Path, topn: int = 10) -> Dict[str, Any]:
    con = sqlite3.connect(db_path)
    try:
        # Load what exists
        have = {}
        for t in ("events", "alarms", "clients", "wlan", "devices", "sites", "users"):
            try:
                have[t] = load_table(con, t)
            except Exception:
                have[t] = []

        # Map client MAC -> hostname from clients table
        mac_to_host: Dict[str, str] = {}
        for c in have.get("clients", []):
            mac = str(c.get("mac", "")).lower()
            host = c.get("hostname") or c.get("name") or c.get("device_name")
            if mac:
                mac_to_host[mac] = str(host) if host else ""

        # Top SSIDs: derive from events ssid or wlan names fallback
        ssid_counts: collections.Counter[str] = collections.Counter()
        for e in have.get("events", []):
            ssid = e.get("ssid") or e.get("essid")
            if ssid:
                ssid_counts[str(ssid)] += 1
        # Fallback to wlan names if no events had ssid
        if not ssid_counts and have.get("wlan"):
            for w in have.get("wlan", []):
                name = w.get("name") or w.get("essid")
                if name:
                    ssid_counts[str(name)] += 0

        # Most active clients: by events referencing user (MAC) or hostname
        client_counts: collections.Counter[str] = collections.Counter()
        for e in have.get("events", []):
            mac = str(e.get("user", "")).lower()
            if mac:
                client_counts[mac] += 1
        # Prepare labeled list MAC [hostname]
        client_top: List[Tuple[str, int]] = []
        for mac, cnt in client_counts.most_common(topn):
            host = mac_to_host.get(mac, "")
            label = f"{mac} ({host})" if host else mac
            client_top.append((label, cnt))

        # Frequent alarms: by key/type/subsystem/msg
        alarm_counts: collections.Counter[str] = collections.Counter()
        for a in have.get("alarms", []):
            key = (
                a.get("key") or a.get("type") or a.get("subsystem") or a.get("category")
            )
            if not key:
                key = (a.get("msg") or "").split(".")[0]
            if key:
                alarm_counts[str(key)] += 1

        summary: Dict[str, Any] = {
            "totals": {k: len(v) for k, v in have.items()},
            "top_ssids": top_k(ssid_counts, topn),
            "top_clients": client_top,
            "top_alarms": top_k(alarm_counts, topn),
        }
        return summary
    finally:
        con.close()


def render_markdown(summary: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# UniFi 7-day Report")
    t = summary.get("totals", {})
    lines.append("")
    lines.append("## Totals")
    for k in ("users", "devices", "clients", "events", "alarms", "wlan", "sites"):
        if k in t:
            lines.append(f"- {k}: {t[k]}")
    lines.append("")

    def section(title: str, items: List[Tuple[str, int]]):
        lines.append(f"## {title}")
        if not items:
            lines.append("- (no data)")
        else:
            for name, count in items:
                lines.append(f"- {name}: {count}")
        lines.append("")

    section("Top SSIDs", summary.get("top_ssids", []))
    section("Most Active Clients", summary.get("top_clients", []))
    section("Frequent Alarms", summary.get("top_alarms", []))
    return "\n".join(lines)


def run() -> int:
    ap = argparse.ArgumentParser(
        description="Generate UniFi summary report from SQLite DB"
    )
    ap.add_argument("--db", required=True, help="Path to SQLite DB produced by loader")
    ap.add_argument("--out-md", help="Output Markdown path (default: alongside DB)")
    ap.add_argument("--out-json", help="Output JSON path (default: alongside DB)")
    ap.add_argument("--top", type=int, default=10, help="Top-N for each section")
    args = ap.parse_args()

    db_path = pathlib.Path(args.db)
    summary = summarize(db_path, topn=args.top)
    md = render_markdown(summary)

    out_md = pathlib.Path(args.out_md) if args.out_md else db_path.with_suffix(".md")
    out_json = (
        pathlib.Path(args.out_json) if args.out_json else db_path.with_suffix(".json")
    )
    out_md.write_text(md, encoding="utf-8")
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote report: {out_md}")
    print(f"Wrote JSON:   {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
