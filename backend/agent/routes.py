from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.agent.auth import verify_agent_token
from backend.schemas import (
    ExchangeRequest,
    GrantResponse,
    ReleaseRequest,
    RevokeAgentRequest,
    SecretRequest,
    SecretResponse,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# session_manager is injected at startup from main.py
_manager = None


def set_session_manager(manager) -> None:
    global _manager
    _manager = manager


@router.post("/request-secret", response_model=GrantResponse)
async def request_secret(
    body: SecretRequest,
    request: Request,
    _token: str = Depends(verify_agent_token),
):
    """Phase 1: Request a credential grant. Returns a grant_id (no secret value).

    The grant_id can then be exchanged for the actual secret via POST /agent/exchange.
    """
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
        status = 429 if result["error"] == "rate_limited" else 403
        raise HTTPException(status_code=status, detail=result)

    return GrantResponse(**result)


@router.post("/exchange", response_model=SecretResponse)
async def exchange_secret(
    body: ExchangeRequest,
    request: Request,
    _token: str = Depends(verify_agent_token),
):
    """Phase 2: Exchange a grant_id for the actual secret value.

    Each exchange decrements uses_remaining. When exhausted, the grant is auto-revoked.
    """
    source_ip = request.client.host if request.client else ""
    result = await _manager.exchange_grant(body.grant_id, source_ip=source_ip)

    if "error" in result:
        codes = {"not_found": 404, "revoked": 410, "expired": 410, "exhausted": 410}
        raise HTTPException(
            status_code=codes.get(result["error"], 400),
            detail=result,
        )

    return SecretResponse(**result)


@router.post("/release")
async def release_secret(
    body: ReleaseRequest,
    _token: str = Depends(verify_agent_token),
):
    """Release a grant early, revoking access before TTL expiry."""
    result = await _manager.release_grant(body.grant_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/revoke-agent")
async def revoke_agent(
    body: RevokeAgentRequest,
    _token: str = Depends(verify_agent_token),
):
    """Revoke ALL active grants for an agent. Used for incident response."""
    result = await _manager.revoke_agent(body.agent_name)
    return result
