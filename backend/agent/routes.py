from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.agent.auth import verify_agent_token
from backend.schemas import (
    DeniedResponse,
    ReleaseRequest,
    SecretRequest,
    SecretResponse,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# session_manager is injected at startup from main.py
_manager = None


def set_session_manager(manager) -> None:
    global _manager
    _manager = manager


@router.post("/request-secret")
async def request_secret(
    body: SecretRequest,
    request: Request,
    _token: str = Depends(verify_agent_token),
):
    source_ip = request.client.host if request.client else ""
    result = await _manager.request_grant(
        agent_name=body.agent_name,
        environment=body.environment,
        task=body.task,
        secret_ref=body.secret_ref,
        requested_ttl=body.requested_ttl,
        source_ip=source_ip,
    )

    if "error" in result:
        raise HTTPException(status_code=403, detail=result)

    return SecretResponse(**result)


@router.post("/release")
async def release_secret(
    body: ReleaseRequest,
    _token: str = Depends(verify_agent_token),
):
    result = await _manager.release_grant(body.grant_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result)
    return result
