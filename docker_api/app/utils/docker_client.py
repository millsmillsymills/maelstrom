from __future__ import annotations

import docker
from docker import DockerClient
from docker.client import APIClient
from functools import lru_cache


@lru_cache(maxsize=1)
def get_client() -> DockerClient:
    """Get high-level Docker client (cached)."""
    return docker.from_env()


@lru_cache(maxsize=1)
def get_low_level_client() -> APIClient:
    """Get low-level Docker API client (cached)."""
    return docker.APIClient(base_url=get_client().api.base_url)
