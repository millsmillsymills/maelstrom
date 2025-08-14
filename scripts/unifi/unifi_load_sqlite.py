#!/usr/bin/env python3
"""
Load UniFi export JSONs into a simple SQLite database for analysis.

Creates per-resource tables with minimal schema and stores raw JSON:
  - tables: sites, devices, clients, users, events, alarms, wlan
  - columns: id TEXT, ts_ms INTEGER NULL, data TEXT

The loader tries common id fields: _id, id, mac, user_id, ap_mac.
For events, ts_ms is populated from 'time' when present.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
from typing import Any, Dict, List, Optional


RESOURCES = ("sites", "devices", "clients", "users", "events", "alarms", "wlan")


def guess_id(obj: Dict[str, Any]) -> Optional[str]:
    for k in ("_id", "id", "mac", "user_id", "ap_mac"):
        v = obj.get(k)
        if isinstance(v, str) and v:
            return v
    # fallback: some objects have key "name" unique within a site
    v = obj.get("name")
    if isinstance(v, str) and v:
        return v
    return None


def events_ts_ms(obj: Dict[str, Any]) -> Optional[int]:
    v = obj.get("time")
    if isinstance(v, (int, float)):
        return int(v)
    return None


def ensure_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for table in RESOURCES:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT,
                ts_ms INTEGER,
                data TEXT NOT NULL
            )
            """
        )
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_id ON {table}(id)")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_ts ON {table}(ts_ms)")
    conn.commit()

    # Normalized helper tables (optional population)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clients_norm (
            mac TEXT,
            ip TEXT,
            hostname TEXT,
            first_seen_ms INTEGER,
            last_seen_ms INTEGER,
            raw_id TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_clients_norm_mac ON clients_norm(mac)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS devices_norm (
            mac TEXT,
            name TEXT,
            ip TEXT,
            model TEXT,
            version TEXT,
            raw_id TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_devices_norm_mac ON devices_norm(mac)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events_norm (
            ts_ms INTEGER,
            mac TEXT,
            ap_mac TEXT,
            ssid TEXT,
            key TEXT,
            raw_id TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_norm_ts ON events_norm(ts_ms)")
    conn.commit()


def load_resource(
    conn: sqlite3.Connection, resource: str, items: List[Dict[str, Any]]
) -> int:
    cur = conn.cursor()
    rows: List[tuple] = []
    for obj in items:
        rid = guess_id(obj)
        ts = events_ts_ms(obj) if resource == "events" else None
        rows.append((rid, ts, json.dumps(obj, ensure_ascii=False)))
    cur.executemany(f"INSERT INTO {resource} (id, ts_ms, data) VALUES (?, ?, ?)", rows)
    return len(rows)


def populate_normalized(conn: sqlite3.Connection, present: List[str]) -> None:
    cur = conn.cursor()
    if "clients" in present:
        # Clear and repopulate
        cur.execute("DELETE FROM clients_norm")
        rows = cur.execute("SELECT id, data FROM clients").fetchall()
        out = []
        for rid, data in rows:
            try:
                obj = json.loads(data)
            except Exception:
                continue
            mac = (obj.get("mac") or "").lower()
            ip = obj.get("ip") or obj.get("network") or None
            hostname = obj.get("hostname") or obj.get("name") or obj.get("device_name")
            first_seen = obj.get("first_seen") or obj.get("first_seen_ms")
            last_seen = obj.get("last_seen") or obj.get("last_seen_ms")
            out.append((mac, ip, hostname, first_seen, last_seen, rid))
        cur.executemany(
            "INSERT INTO clients_norm (mac, ip, hostname, first_seen_ms, last_seen_ms, raw_id) VALUES (?,?,?,?,?,?)",
            out,
        )
    if "devices" in present:
        cur.execute("DELETE FROM devices_norm")
        rows = cur.execute("SELECT id, data FROM devices").fetchall()
        out = []
        for rid, data in rows:
            try:
                obj = json.loads(data)
            except Exception:
                continue
            mac = (obj.get("mac") or "").lower()
            name = obj.get("name") or obj.get("device_name") or obj.get("hostname")
            ip = obj.get("ip") or obj.get("inform_ip")
            model = obj.get("model") or obj.get("type")
            ver = obj.get("version") or obj.get("fw_caps")
            out.append((mac, name, ip, model, ver, rid))
        cur.executemany(
            "INSERT INTO devices_norm (mac, name, ip, model, version, raw_id) VALUES (?,?,?,?,?,?)",
            out,
        )
    if "events" in present:
        cur.execute("DELETE FROM events_norm")
        rows = cur.execute("SELECT id, data FROM events").fetchall()
        out = []
        for rid, data in rows:
            try:
                obj = json.loads(data)
            except Exception:
                continue
            ts = obj.get("time")
            mac = (obj.get("user") or "").lower()
            ap_mac = (obj.get("ap") or obj.get("ap_mac") or "").lower()
            ssid = obj.get("ssid") or obj.get("essid")
            key = obj.get("key") or obj.get("subsystem") or obj.get("event")
            out.append((ts, mac, ap_mac, ssid, key, rid))
        cur.executemany(
            "INSERT INTO events_norm (ts_ms, mac, ap_mac, ssid, key, raw_id) VALUES (?,?,?,?,?,?)",
            out,
        )
    conn.commit()


def run() -> int:
    ap = argparse.ArgumentParser(description="Load UniFi export JSONs into SQLite")
    ap.add_argument(
        "--export-dir", required=True, help="Directory containing JSON exports"
    )
    ap.add_argument(
        "--db", help="SQLite DB path (default: <export-dir>/unifi_export.db)"
    )
    ap.add_argument(
        "--only",
        help="Comma-separated list of resources to load (default: load all present)",
    )
    ap.add_argument(
        "--normalize", action="store_true", help="Populate normalized helper tables"
    )
    ap.add_argument(
        "--vacuum", action="store_true", help="VACUUM the database after load"
    )
    args = ap.parse_args()

    export_dir = pathlib.Path(args.export_dir).resolve()
    if not export_dir.is_dir():
        print(f"Export dir not found: {export_dir}")
        return 2
    db_path = pathlib.Path(args.db) if args.db else export_dir / "unifi_export.db"

    conn = sqlite3.connect(db_path)
    try:
        ensure_tables(conn)
        total = 0
        # Determine which resources to load
        if args.only:
            only = [r.strip().lower() for r in args.only.split(",") if r.strip()]
            invalid = [r for r in only if r not in RESOURCES]
            if invalid:
                print(f"Invalid resource(s) for --only: {', '.join(invalid)}")
                return 2
            res_list = only
        else:
            res_list = list(RESOURCES)

        present = []
        for res in res_list:
            json_path = export_dir / f"{res}.json"
            if not json_path.exists():
                continue
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "data" in data:
                items = data["data"]
            else:
                items = list(data) if isinstance(data, list) else []
            count = load_resource(conn, res, items)
            print(f"Loaded {count:5d} -> {res}")
            total += count
            present.append(res)
        conn.commit()
        if args.normalize:
            populate_normalized(conn, present)
            print("Populated normalized tables where applicable")
        if args.vacuum:
            # Ensure all transactions are committed before VACUUM
            conn.commit()
            try:
                conn.execute("VACUUM")
                print("VACUUM completed")
            except Exception as e:
                print(f"VACUUM failed: {e}")
        print(f"SQLite DB: {db_path} (total rows {total})")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
