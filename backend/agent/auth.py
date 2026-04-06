from __future__ import annotations

from fastapi import Header, HTTPException

from backend.config import settings


async def verify_agent_token(authorization: str = Header(...)) -> str:
    """FastAPI dependency: validate Bearer token for agent API calls."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.agent_token:
        raise HTTPException(status_code=403, detail="Invalid agent token")

    return token
