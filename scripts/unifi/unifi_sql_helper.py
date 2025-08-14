#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from typing import List, Tuple


def q(con: sqlite3.Connection, sql: str, params: tuple = ()) -> List[tuple]:
    cur = con.cursor()
    return cur.execute(sql, params).fetchall()


def top_clients(con: sqlite3.Connection, limit: int) -> List[Tuple[str, int]]:
    sql = """
    SELECT COALESCE(c.hostname, ''), e.mac, COUNT(*) AS cnt
    FROM events_norm e
    LEFT JOIN clients_norm c ON lower(e.mac) = lower(c.mac)
    WHERE e.mac <> ''
    GROUP BY e.mac
    ORDER BY cnt DESC
    LIMIT ?
    """
    rows = q(con, sql, (limit,))
    return [(f"{mac} ({host})" if host else mac, cnt) for (host, mac, cnt) in rows]


def top_ssids(con: sqlite3.Connection, limit: int) -> List[Tuple[str, int]]:
    sql = """
    SELECT ssid, COUNT(*) AS cnt
    FROM events_norm
    WHERE ssid IS NOT NULL AND ssid <> ''
    GROUP BY ssid
    ORDER BY cnt DESC
    LIMIT ?
    """
    return q(con, sql, (limit,))


def top_alarms(con: sqlite3.Connection, limit: int) -> List[Tuple[str, int]]:
    # Alarms are raw; events_norm carries key, but alarms live in raw table only
    # so a heuristic: group by key inside alarms JSON via LIKE would be expensive.
    # Recommend relying on report JSON instead. Here we show event keys.
    sql = """
    SELECT key, COUNT(*) AS cnt
    FROM events_norm
    WHERE key IS NOT NULL AND key <> ''
    GROUP BY key
    ORDER BY cnt DESC
    LIMIT ?
    """
    return q(con, sql, (limit,))


def run() -> int:
    ap = argparse.ArgumentParser(description="Quick SQL helper for normalized UniFi DB")
    ap.add_argument("--db", required=True, help="Path to SQLite DB")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        print("Top clients:")
        for label, cnt in top_clients(con, args.top):
            print(f"  {label}: {cnt}")
        print("\nTop SSIDs:")
        for ssid, cnt in top_ssids(con, args.top):
            print(f"  {ssid}: {cnt}")
        print("\nTop event keys:")
        for key, cnt in top_alarms(con, args.top):
            print(f"  {key}: {cnt}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
