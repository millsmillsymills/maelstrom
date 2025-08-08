from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContainerStats:
    cpu_percent: Optional[float] = None
    mem_usage: Optional[int] = None
    mem_limit: Optional[int] = None
    mem_percent: Optional[float] = None
    io_read: Optional[int] = None
    io_write: Optional[int] = None
    net_rx: Optional[int] = None
    net_tx: Optional[int] = None


def _calc_cpu_percent(stats: dict) -> Optional[float]:
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        if system_delta > 0 and cpu_delta > 0:
            cores = len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) or 1
            return (cpu_delta / system_delta) * cores * 100.0
    except Exception:
        return None
    return None


def collect_container_stats_once(container) -> Optional[ContainerStats]:
    try:
        stats = container.stats(stream=False)
        cpu_percent = _calc_cpu_percent(stats)
        mem_usage = int(stats["memory_stats"].get("usage", 0))
        mem_limit = int(stats["memory_stats"].get("limit", 0)) or None
        mem_percent = (mem_usage / mem_limit * 100.0) if mem_limit else None

        # I/O
        blkio = stats.get("blkio_stats", {}).get("io_service_bytes_recursive", [])
        io_read = io_write = 0
        for item in blkio:
            if item.get("op") == "Read":
                io_read += int(item.get("value", 0))
            elif item.get("op") == "Write":
                io_write += int(item.get("value", 0))

        # Network
        net = stats.get("networks", {}) or {}
        net_rx = sum(int(v.get("rx_bytes", 0)) for v in net.values()) if isinstance(net, dict) else None
        net_tx = sum(int(v.get("tx_bytes", 0)) for v in net.values()) if isinstance(net, dict) else None

        return ContainerStats(
            cpu_percent=cpu_percent,
            mem_usage=mem_usage,
            mem_limit=mem_limit,
            mem_percent=mem_percent,
            io_read=io_read or None,
            io_write=io_write or None,
            net_rx=net_rx,
            net_tx=net_tx,
        )
    except Exception:
        return None

