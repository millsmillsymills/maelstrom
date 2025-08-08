from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ContainerSummary(BaseModel):
    id: str
    name: str
    image: str
    status: Optional[str]
    ports: Dict[str, Any] = Field(default_factory=dict)
    labels: Dict[str, str] = Field(default_factory=dict)
    created: Optional[datetime]
    cpu_percent: Optional[float]
    mem_usage: Optional[int]
    mem_limit: Optional[int]
    mem_percent: Optional[float]


class ContainerDetail(BaseModel):
    id: str
    name: str
    image: str
    status: Optional[str]
    health: Optional[str]
    uptime_seconds: Optional[float]
    mounts: List[Dict[str, Any]] = Field(default_factory=list)
    networks: Dict[str, Any] = Field(default_factory=dict)
    cpu_percent: Optional[float]
    mem_usage: Optional[int]
    mem_limit: Optional[int]
    mem_percent: Optional[float]
    io_read: Optional[int]
    io_write: Optional[int]
    net_rx: Optional[int]
    net_tx: Optional[int]
    logs: List[str] = Field(default_factory=list)


class ContainerActionResponse(BaseModel):
    container_id: str
    action: str
    status: str


class SystemInfo(BaseModel):
    docker_version: Optional[str]
    api_version: Optional[str]
    os: Optional[str]
    architecture: Optional[str]
    kernel_version: Optional[str]
    containers_total: Optional[int]
    containers_running: Optional[int]
    images: Optional[int]
    cpu_percent: Optional[float]
    mem_total: Optional[int]
    mem_available: Optional[int]
    mem_percent: Optional[float]
    timestamp: datetime


class DockerImageSummary(BaseModel):
    id: str
    tags: List[str]
    size: Optional[int]
    created: Optional[str]


class ExecRequest(BaseModel):
    cmd: List[str]


class ExecResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str

