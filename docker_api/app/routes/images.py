from __future__ import annotations

from typing import List

from fastapi import APIRouter

from ..utils.docker_client import get_client
from ..models.schemas import DockerImageSummary


router = APIRouter()


@router.get("/images", response_model=List[DockerImageSummary])
def list_images_root():
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
