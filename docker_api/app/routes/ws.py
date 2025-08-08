from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger

from ..utils.docker_client import get_low_level_client


router = APIRouter()


@router.websocket("/ws/logs/{container_id}")
async def logs_ws(websocket: WebSocket, container_id: str, keyword: Optional[str] = Query(None), tail: int = Query(100)):
    # Simple API key check for WebSocket: use Authorization header or token query.
    from ..utils.auth import _get_api_key
    api_key = _get_api_key()
    auth = websocket.headers.get("authorization") or websocket.query_params.get("token")
    if not api_key or not auth or (auth.lower().startswith("bearer ") and auth.split(" ", 1)[1] != api_key) and auth != api_key:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    cli = get_low_level_client()
    try:
        stream = cli.attach(container=container_id, stdout=True, stderr=True, stream=True, logs=True, demux=True)
        sent = 0
        async def send_line(line: str, source: str):
            nonlocal sent
            if keyword and keyword not in line:
                return
            await websocket.send_json({"source": source, "message": line})
            sent += 1

        for out, err in stream:
            if out:
                line = out.decode("utf-8", errors="ignore")
                await send_line(line, "stdout")
            if err:
                line = err.decode("utf-8", errors="ignore")
                await send_line(line, "stderr")
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket log streaming failed")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
        await websocket.close()
