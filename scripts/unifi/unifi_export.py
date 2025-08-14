#!/usr/bin/env python3
"""
UniFi Data Export Toolkit

Exports data from UniFi Network (UniFi OS or legacy Controller) to JSON/CSV.

Features:
- Auto-detects UniFi OS vs legacy auth endpoints.
- Supports resources: sites, devices, clients, users, events, alarms, wlan.
- Time range filters for events.
- Writes timestamped export folders; format json/csv/both.

Configuration:
- Read from CLI flags or environment variables:
  UNIFI_URL | UP_UNIFI_URL
  UNIFI_USER | UP_UNIFI_USERNAME
  UNIFI_PASS | UP_UNIFI_PASSWORD
  UNIFI_SITE (default: "default")
  UNIFI_INSECURE | UP_UNIFI_INSECURE (true/false)

Security: do not commit real secrets. Place them under secrets/ with 0600 perms.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import json
import os
import pathlib
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - surfaced at runtime if missing
    print(
        "Missing dependency: requests. Install with `pip install -r scripts/unifi/requirements.txt`.",
        file=sys.stderr,
    )
    raise


# ---------------------------- Utility helpers ---------------------------- #


def parse_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def epoch_ms(dt_obj: dt.datetime) -> int:
    return int(dt_obj.timestamp() * 1000)


def parse_time(s: str) -> dt.datetime:
    """Parse time values like '2024-01-01T00:00:00Z', '2024-01-01', '2h', '30m', '7d'.

    Relative values are relative to now (UTC) and subtract the duration.
    """
    s = s.strip()
    now = dt.datetime.now(dt.timezone.utc)
    # relative forms
    if s.endswith("m") and s[:-1].isdigit():
        return now - dt.timedelta(minutes=int(s[:-1]))
    if s.endswith("h") and s[:-1].isdigit():
        return now - dt.timedelta(hours=int(s[:-1]))
    if s.endswith("d") and s[:-1].isdigit():
        return now - dt.timedelta(days=int(s[:-1]))
    # epoch seconds or ms
    if s.isdigit():
        if len(s) > 10:  # ms
            return dt.datetime.fromtimestamp(int(s) / 1000, tz=dt.timezone.utc)
        return dt.datetime.fromtimestamp(int(s), tz=dt.timezone.utc)
    # ISO8601 or date
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"Invalid time value: {s}") from exc


def ensure_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def flatten_record(d: Dict[str, Any], *, max_depth: int = 1) -> Dict[str, Any]:
    """Flatten a dict for CSV output. Nested dicts beyond max_depth are JSON-encoded.

    This keeps keys deterministic and avoids exploding schemas for deeply nested fields.
    """
    out: Dict[str, Any] = {}

    def _walk(prefix: str, obj: Any, depth: int) -> None:
        if isinstance(obj, dict) and depth <= max_depth:
            for k, v in obj.items():
                _walk(f"{prefix}{k}." if prefix else f"{k}.", v, depth + 1)
        else:
            key = prefix[:-1] if prefix.endswith(".") else prefix
            if isinstance(obj, (dict, list)):
                out[key] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            else:
                out[key] = obj

    _walk("", d, 0)
    return out


# ---------------------------- UniFi API client --------------------------- #


class UniFiAuth:
    """Lightweight container for UniFi auth/session state.

    Avoids dataclass to ensure import safety when this module is loaded
    dynamically (pytest imports via importlib without sys.modules entry).
    """

    def __init__(
        self,
        *,
        base_url: str,
        site: str = "default",
        insecure: bool = False,
        cookie_jar: "requests.sessions.RequestsCookieJar | None" = None,
        csrf_token: Optional[str] = None,
        is_unifi_os: bool = False,
    ) -> None:
        self.base_url = base_url
        self.site = site
        self.insecure = insecure
        self.cookie_jar = cookie_jar
        self.csrf_token = csrf_token
        self.is_unifi_os = is_unifi_os


class UniFiClient:
    def __init__(self, auth: UniFiAuth):
        self.auth = auth
        self.session = requests.Session()
        if auth.cookie_jar is not None:
            self.session.cookies = auth.cookie_jar

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.auth.csrf_token:
            h["X-CSRF-Token"] = self.auth.csrf_token
        return h

    def login(self, username: str, password: str, timeout: int = 15) -> None:
        base = self.auth.base_url.rstrip("/")
        payload = {"username": username, "password": password}
        # Prefer UniFi OS
        url_os = f"{base}/api/auth/login"
        r = self.session.post(
            url_os,
            json=payload,
            headers=self._headers(),
            verify=not self.auth.insecure,
            timeout=timeout,
        )
        if r.status_code == 200:
            # Obtain CSRF token if present
            self.auth.is_unifi_os = True
            self.auth.cookie_jar = self.session.cookies
            self.auth.csrf_token = r.headers.get(
                "X-Csrf-Token"
            ) or self.session.headers.get("X-CSRF-Token")
            return
        # Fallback legacy
        url_legacy = f"{base}/api/login"
        r2 = self.session.post(
            url_legacy,
            json=payload,
            headers=self._headers(),
            verify=not self.auth.insecure,
            timeout=timeout,
        )
        if r2.status_code == 200:
            self.auth.is_unifi_os = False
            self.auth.cookie_jar = self.session.cookies
            return
        raise RuntimeError(
            f"UniFi login failed: OS={r.status_code} legacy={r2.status_code}"
        )

    # Endpoint builder
    def _api_base(self) -> str:
        base = self.auth.base_url.rstrip("/")
        if self.auth.is_unifi_os:
            return f"{base}/proxy/network/api"
        return f"{base}/api"

    def _site_path(self) -> str:
        return f"/s/{self.auth.site}"

    # Fetch helpers
    def get(
        self, path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30
    ) -> Dict[str, Any]:
        url = f"{self._api_base()}{path}"
        r = self.session.get(
            url,
            headers=self._headers(),
            params=params,
            verify=not self.auth.insecure,
            timeout=timeout,
        )
        if r.status_code != 200:
            raise RuntimeError(f"GET {path} -> HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    # Resource methods
    def sites(self) -> List[Dict[str, Any]]:
        data = self.get("/self/sites")
        return data.get("data", data)  # some endpoints return {data: []}

    def devices(self) -> List[Dict[str, Any]]:
        data = self.get(f"{self._site_path()}/stat/device")
        return data.get("data", data)

    def clients(self) -> List[Dict[str, Any]]:
        data = self.get(f"{self._site_path()}/stat/sta")
        return data.get("data", data)

    def users(self) -> List[Dict[str, Any]]:
        data = self.get(f"{self._site_path()}/list/user")
        return data.get("data", data)

    def wlan(self) -> List[Dict[str, Any]]:
        data = self.get(f"{self._site_path()}/list/wlanconf")
        return data.get("data", data)

    def alarms(self) -> List[Dict[str, Any]]:
        # Older: list/alert; newer: stat/alarm
        try:
            data = self.get(f"{self._site_path()}/stat/alarm")
            return data.get("data", data)
        except Exception:
            data = self.get(f"{self._site_path()}/list/alert")
            return data.get("data", data)

    def events(
        self,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"_sort": "-time", "_limit": limit}
        if start_ms is not None:
            params["start"] = start_ms
        if end_ms is not None:
            params["end"] = end_ms
        data = self.get(f"{self._site_path()}/stat/event", params=params)
        return data.get("data", data)


# ---------------------------- Export pipeline ---------------------------- #


RESOURCES = (
    "sites",
    "devices",
    "clients",
    "users",
    "events",
    "alarms",
    "wlan",
)


def write_json(path: pathlib.Path, items: List[Dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def write_csv(path: pathlib.Path, items: List[Dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    rows = [flatten_record(i) for i in items]
    # Aggregate headers
    headers: List[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                headers.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def resolve_env() -> Tuple[str, str, str, str, bool]:
    url = os.environ.get("UP_UNIFI_URL") or os.environ.get("UNIFI_URL") or ""
    user = os.environ.get("UP_UNIFI_USERNAME") or os.environ.get("UNIFI_USER") or ""
    pw = os.environ.get("UP_UNIFI_PASSWORD") or os.environ.get("UNIFI_PASS") or ""
    site = os.environ.get("UNIFI_SITE") or "default"
    insecure = parse_bool(
        os.environ.get("UP_UNIFI_INSECURE") or os.environ.get("UNIFI_INSECURE"), False
    )
    return url, user, pw, site, insecure


def run() -> int:
    parser = argparse.ArgumentParser(description="Export data from UniFi Controller")
    parser.add_argument("--url", help="Base URL of UniFi (e.g., https://192.168.1.2)")
    parser.add_argument("--user", help="Username")
    parser.add_argument("--password", help="Password (or prompt)")
    parser.add_argument(
        "--site", default=None, help="Site name (default: env or 'default')"
    )
    parser.add_argument(
        "--insecure", action="store_true", help="Disable TLS verification"
    )
    parser.add_argument(
        "--resources",
        default="all",
        help="Comma list of resources to export (all|" + ",".join(RESOURCES) + ")",
    )
    parser.add_argument("--format", choices=["json", "csv", "both"], default="json")
    parser.add_argument(
        "--since",
        default="24h",
        help="Time window start for events (e.g., 24h, 2024-01-01)",
    )
    parser.add_argument(
        "--until", default=None, help="Time window end for events (default: now)"
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default: output/unifi/YYYYmmdd_HHMMSS)",
    )
    args = parser.parse_args()

    env_url, env_user, env_pw, env_site, env_insecure = resolve_env()

    base_url = (args.url or env_url or "").rstrip("/")
    if not base_url:
        print("Missing --url or UNIFI_URL/UP_UNIFI_URL", file=sys.stderr)
        return 2

    user = args.user or env_user
    if not user:
        print("Missing --user or UNIFI_USER/UP_UNIFI_USERNAME", file=sys.stderr)
        return 2

    password = args.password or env_pw or getpass.getpass("UniFi password: ")
    site = args.site or env_site or "default"
    insecure = args.insecure or env_insecure

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = pathlib.Path(args.out_dir or f"output/unifi/{ts}")
    ensure_dir(out_dir)

    auth = UniFiAuth(base_url=base_url, site=site, insecure=insecure)
    client = UniFiClient(auth)
    client.login(user, password)

    # Determine resources
    if args.resources.strip().lower() == "all":
        resources = list(RESOURCES)
    else:
        parts = [p.strip().lower() for p in args.resources.split(",") if p.strip()]
        invalid = [p for p in parts if p not in RESOURCES]
        if invalid:
            print(f"Invalid resource(s): {', '.join(invalid)}", file=sys.stderr)
            return 2
        resources = parts

    # Time window for events
    start_dt = parse_time(args.since) if args.since else None
    end_dt = parse_time(args.until) if args.until else dt.datetime.now(dt.timezone.utc)
    start_ms = epoch_ms(start_dt) if start_dt else None
    end_ms = epoch_ms(end_dt) if end_dt else None

    fmt = args.format

    exported: Dict[str, int] = {}
    for res in resources:
        if res == "sites":
            items = client.sites()
        elif res == "devices":
            items = client.devices()
        elif res == "clients":
            items = client.clients()
        elif res == "users":
            items = client.users()
        elif res == "wlan":
            items = client.wlan()
        elif res == "alarms":
            items = client.alarms()
        elif res == "events":
            items = client.events(start_ms=start_ms, end_ms=end_ms)
        else:  # pragma: no cover - defensive
            continue

        exported[res] = len(items)
        stem = out_dir / f"{res}"
        if fmt in ("json", "both"):
            write_json(stem.with_suffix(".json"), items)
        if fmt in ("csv", "both"):
            write_csv(stem.with_suffix(".csv"), items)

    summary_path = out_dir / "summary.json"
    write_json(
        summary_path, [{"resource": k, "count": v} for k, v in sorted(exported.items())]
    )

    print(f"Export complete -> {out_dir}")
    for k, v in sorted(exported.items()):
        print(f"  - {k}: {v}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
