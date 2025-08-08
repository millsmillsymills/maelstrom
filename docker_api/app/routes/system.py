from __future__ import annotations

from datetime import datetime
from typing import List

import platform
import psutil
from fastapi import APIRouter
from loguru import logger

from ..utils.docker_client import get_client
from ..models.schemas import SystemInfo, DockerImageSummary


router = APIRouter()


@router.get("/info", response_model=SystemInfo)
def system_info():
    client = get_client()
    d_info = client.info()
    version = client.version()

    cpu = psutil.cpu_percent(interval=0.2)
    vm = psutil.virtual_memory()

    return SystemInfo(
        docker_version=version.get("Version"),
        api_version=version.get("ApiVersion"),
        os=platform.platform(),
        architecture=d_info.get("Architecture"),
        kernel_version=d_info.get("KernelVersion"),
        containers_total=d_info.get("Containers"),
        containers_running=d_info.get("ContainersRunning"),
        images=d_info.get("Images"),
        cpu_percent=cpu,
        mem_total=vm.total,
        mem_available=vm.available,
        mem_percent=vm.percent,
        timestamp=datetime.utcnow(),
    )


@router.get("/images", response_model=List[DockerImageSummary])
def list_images():
    client = get_client()
    images = client.images.list()
    results: List[DockerImageSummary] = []
    for img in images:
        tags = img.tags or [img.short_id]
        created = getattr(img, "attrs", {}).get("Created")
        results.append(
            DockerImageSummary(
                id=img.id,
                tags=tags,
                size=img.attrs.get("Size"),
                created=created,
            )
        )
    return results

