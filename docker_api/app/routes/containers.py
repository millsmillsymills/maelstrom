from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from ..utils.docker_client import get_client
from ..utils.stats import collect_container_stats_once
from ..models.schemas import (
    ContainerSummary,
    ContainerDetail,
    ContainerActionResponse,
)


router = APIRouter()


def _match_filters(
    container, status: Optional[str], label: Optional[str], name_regex: Optional[str]
) -> bool:
    try:
        c_status = (container.status or "").lower()
        if status and c_status != status.lower():
            return False
        if label:
            labels = container.labels or {}
            if label not in labels and not any(
                k == label or f"{k}={v}" == label for k, v in labels.items()
            ):
                return False
        if name_regex:
            pattern = re.compile(name_regex)
            names: List[str] = []
            # Primary name
            if getattr(container, "name", None):
                names.append(container.name.lstrip("/"))
            # Attributes: single name and list of names
            attrs = getattr(container, "attrs", {}) or {}
            single = attrs.get("Name", "")
            if isinstance(single, str) and single:
                names.append(single.lstrip("/"))
            raw_names = attrs.get("Names", [])
            if isinstance(raw_names, list):
                names.extend([str(n).lstrip("/") for n in raw_names if n])
            if not any(pattern.search(n or "") for n in names if n):
                return False
        return True
    except Exception:
        return False


@router.get("", response_model=List[ContainerSummary])
def list_containers(
    status: Optional[str] = Query(
        None, description="Filter by status e.g., running, exited"
    ),
    label: Optional[str] = Query(None, description="Filter by label or 'key=value'"),
    name_regex: Optional[str] = Query(
        None, description="Filter by container name regex"
    ),
):
    client = get_client()
    containers = client.containers.list(all=True)
    results: List[ContainerSummary] = []
    for c in containers:
        if not _match_filters(c, status, label, name_regex):
            continue
        stats = collect_container_stats_once(c)
        created = (
            datetime.fromtimestamp(
                (
                    c.attrs.get("Created", 0)
                    if isinstance(c.attrs.get("Created", 0), (int, float))
                    else 0
                ),
                tz=timezone.utc,
            )
            if isinstance(c.attrs.get("Created", 0), (int, float))
            else (
                datetime.fromisoformat(c.attrs.get("Created").replace("Z", "+00:00"))
                if c.attrs.get("Created")
                else None
            )
        )
        results.append(
            ContainerSummary(
                id=c.id,
                name=c.name,
                image=(
                    c.image.tags[0]
                    if c.image and c.image.tags
                    else c.attrs.get("Config", {}).get("Image", "")
                ),
                status=c.status,
                ports=c.attrs.get("NetworkSettings", {}).get("Ports", {}),
                labels=c.labels or {},
                created=created,
                cpu_percent=stats.cpu_percent if stats else None,
                mem_usage=stats.mem_usage if stats else None,
                mem_limit=stats.mem_limit if stats else None,
                mem_percent=stats.mem_percent if stats else None,
            )
        )
    return results


@router.get("/{container_id}", response_model=ContainerDetail)
def get_container(container_id: str):
    client = get_client()
    try:
        c = client.containers.get(container_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Container not found")

    c.reload()
    stats = collect_container_stats_once(c)
    logs = (
        c.logs(tail=100, timestamps=True, stdout=True, stderr=True)
        .decode("utf-8", errors="ignore")
        .splitlines()
    )

    state = c.attrs.get("State", {})
    health = (state.get("Health", {}) or {}).get("Status")
    started_at = state.get("StartedAt")
    uptime_seconds: Optional[float] = None
    if started_at and started_at != "0001-01-01T00:00:00Z":
        try:
            t = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            uptime_seconds = (datetime.now(timezone.utc) - t).total_seconds()
        except Exception:
            uptime_seconds = None

    mounts = c.attrs.get("Mounts", [])
    networks = (c.attrs.get("NetworkSettings", {}) or {}).get("Networks", {})

    return ContainerDetail(
        id=c.id,
        name=c.name,
        image=(
            c.image.tags[0]
            if c.image and c.image.tags
            else c.attrs.get("Config", {}).get("Image", "")
        ),
        status=c.status,
        health=health,
        uptime_seconds=uptime_seconds,
        mounts=mounts,
        networks=networks,
        cpu_percent=stats.cpu_percent if stats else None,
        mem_usage=stats.mem_usage if stats else None,
        mem_limit=stats.mem_limit if stats else None,
        mem_percent=stats.mem_percent if stats else None,
        io_read=stats.io_read if stats else None,
        io_write=stats.io_write if stats else None,
        net_rx=stats.net_rx if stats else None,
        net_tx=stats.net_tx if stats else None,
        logs=logs,
    )


@router.get("/{container_id}/stats")
def container_stats(container_id: str):
    client = get_client()
    try:
        c = client.containers.get(container_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Container not found")
    stats = collect_container_stats_once(c)
    if not stats:
        raise HTTPException(status_code=400, detail="Unable to collect stats")
    return {
        "cpu_percent": stats.cpu_percent,
        "mem_usage": stats.mem_usage,
        "mem_limit": stats.mem_limit,
        "mem_percent": stats.mem_percent,
        "io_read": stats.io_read,
        "io_write": stats.io_write,
        "net_rx": stats.net_rx,
        "net_tx": stats.net_tx,
    }


@router.post("/{container_id}/start", response_model=ContainerActionResponse)
def start_container(container_id: str):
    client = get_client()
    try:
        c = client.containers.get(container_id)
        c.start()
        return ContainerActionResponse(container_id=c.id, action="start", status="ok")
    except Exception as e:
        logger.exception("Failed to start container")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{container_id}/stop", response_model=ContainerActionResponse)
def stop_container(container_id: str):
    client = get_client()
    try:
        c = client.containers.get(container_id)
        c.stop()
        return ContainerActionResponse(container_id=c.id, action="stop", status="ok")
    except Exception as e:
        logger.exception("Failed to stop container")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{container_id}/restart", response_model=ContainerActionResponse)
def restart_container(container_id: str):
    client = get_client()
    try:
        c = client.containers.get(container_id)
        c.restart()
        return ContainerActionResponse(container_id=c.id, action="restart", status="ok")
    except Exception as e:
        logger.exception("Failed to restart container")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{container_id}", response_model=ContainerActionResponse)
def delete_container(container_id: str):
    client = get_client()
    try:
        c = client.containers.get(container_id)
        c.remove(force=True)
        return ContainerActionResponse(container_id=c.id, action="delete", status="ok")
    except Exception as e:
        logger.exception("Failed to delete container")
        raise HTTPException(status_code=400, detail=str(e))
