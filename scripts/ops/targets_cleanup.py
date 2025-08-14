#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGETS_DIR = Path("collections/prometheus/targets")


def ping(host: str, timeout: float = 1.0, count: int = 1) -> bool:
    try:
        # Linux ping; -W in seconds, -c count
        res = subprocess.run(
            ["ping", "-c", str(count), "-W", str(int(timeout)), host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def load_json(path: Path):
    try:
        with path.open() as f:
            return json.load(f)
    except Exception:
        return None


def backup(path: Path):
    ts = time.strftime("%Y%m%d_%H%M%S")
    b = path.with_suffix(path.suffix + f".bak_{ts}")
    shutil.copy2(path, b)
    return b


def sanitize_targets(data):
    # file_sd JSON format: list of {"targets": ["host:port", ...], "labels": {...}}
    changed = False
    for block in data:
        targets = block.get("targets", [])
        new_targets = []
        for t in targets:
            host = t.split(":")[0]
            if ping(host):
                new_targets.append(t)
        if len(new_targets) != len(targets):
            block["targets"] = new_targets
            changed = True
    return changed, data


def main():
    ap = argparse.ArgumentParser(
        description="Prune unreachable targets from file_sd JSONs (dry-run by default)"
    )
    ap.add_argument("--dir", default=str(TARGETS_DIR), help="Targets directory")
    ap.add_argument(
        "--apply", action="store_true", help="Write changes in place with backups"
    )
    ap.add_argument(
        "--files", nargs="*", help="Limit to specific files (e.g., snmp_targets.json)"
    )
    args = ap.parse_args()

    tdir = Path(args.dir)
    if not tdir.is_dir():
        print(f"Targets dir not found: {tdir}", file=sys.stderr)
        return 1

    files = (
        args.files
        if args.files
        else [
            "blackbox_http.json",
            "blackbox_icmp.json",
            "snmp_targets.json",
            "inventory.json",
            "prometheus_targets_dump.json",
        ]
    )

    for name in files:
        p = tdir / name
        if not p.exists():
            continue
        data = load_json(p)
        if not isinstance(data, list):
            continue
        changed, new_data = sanitize_targets(data)
        if not changed:
            print(f"{name}: no changes")
            continue
        print(f"{name}: will prune unreachable targets")
        if args.apply:
            b = backup(p)
            with p.open("w") as f:
                json.dump(new_data, f, indent=2)
            print(f"  wrote {p} (backup {b.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
