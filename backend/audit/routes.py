from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.audit.logger import (
    get_logs,
    get_stats,
    register_ws_client,
    unregister_ws_client,
)
from backend.schemas import AuditLogOut, AuditStats

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogOut])
async def list_logs(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    requester: str | None = None,
    environment: str | None = None,
):
    return await get_logs(
        limit=limit,
        offset=offset,
        action=action,
        requester=requester,
        environment=environment,
    )


@router.get("/stats", response_model=AuditStats)
async def stats():
    return await get_stats()


@router.websocket("/live")
async def live_feed(ws: WebSocket):
    await ws.accept()
    register_ws_client(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive
    except WebSocketDisconnect:
        pass
    finally:
        unregister_ws_client(ws)
