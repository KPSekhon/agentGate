from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from backend.schemas import SSHKeyOut, SSHKeyRegister, SSHKeyRequest

router = APIRouter(prefix="/ssh", tags=["ssh"])

_registry = None


def set_ssh_registry(registry) -> None:
    global _registry
    _registry = registry


@router.get("/keys", response_model=list[SSHKeyOut])
async def list_keys():
    return await _registry.list_keys()


@router.post("/keys", response_model=SSHKeyOut)
async def register_key(body: SSHKeyRegister):
    return await _registry.register_key(
        name=body.name,
        fingerprint=body.fingerprint,
        key_type=body.key_type,
        has_passphrase=body.has_passphrase,
        description=body.description,
    )


@router.post("/keys/request")
async def request_key(body: SSHKeyRequest, request: Request):
    source_ip = request.client.host if request.client else ""
    result = await _registry.request_key(
        requester=body.requester,
        environment=body.environment,
        task=body.task,
        key_name=body.key_name,
        source_ip=source_ip,
    )
    if "error" in result:
        raise HTTPException(status_code=403, detail=result)
    return result
