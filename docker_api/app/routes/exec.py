from __future__ import annotations


from fastapi import APIRouter, HTTPException
from loguru import logger

from ..utils.docker_client import get_client
from ..utils.security import validate_command
from ..models.schemas import ExecRequest, ExecResponse


router = APIRouter()


@router.post("/{container_id}/exec", response_model=ExecResponse)
def exec_in_container(container_id: str, payload: ExecRequest):
    # Validate requested command is safe
    validate_command(payload.cmd)

    client = get_client()
    try:
        c = client.containers.get(container_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Container not found")

    try:
        logger.info(f"Exec in {c.name}: {payload.cmd}")
        res = c.exec_run(payload.cmd, stdout=True, stderr=True)
        stdout = (
            res.output.decode("utf-8", errors="ignore")
            if isinstance(res.output, (bytes, bytearray))
            else str(res.output)
        )
        return ExecResponse(exit_code=res.exit_code, stdout=stdout, stderr="")
    except Exception as e:
        logger.exception("Exec failed")
        raise HTTPException(status_code=400, detail=str(e))
