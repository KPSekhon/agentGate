from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func

from backend.database import async_session
from backend.models import AuditLog
from backend.audit.anomaly import compute_anomaly_score

# WebSocket broadcast set
_ws_clients: set[Any] = set()


def register_ws_client(ws) -> None:
    _ws_clients.add(ws)


def unregister_ws_client(ws) -> None:
    _ws_clients.discard(ws)


async def log_event(
    requester: str,
    environment: str,
    task: str,
    secret_ref: str,
    action: str,
    policy_name: str = "",
    ttl_seconds: int = 0,
    source_ip: str = "",
) -> AuditLog:
    anomaly = await compute_anomaly_score(requester, environment)

    entry = AuditLog(
        requester=requester,
        environment=environment,
        task=task,
        secret_ref=secret_ref,
        action=action,
        policy_name=policy_name,
        ttl_seconds=ttl_seconds,
        source_ip=source_ip,
        anomaly_score=anomaly,
    )

    async with async_session() as session:
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

    # Broadcast to WebSocket clients
    await _broadcast(entry)
    return entry


async def _broadcast(entry: AuditLog) -> None:
    if not _ws_clients:
        return
    import json
    payload = json.dumps({
        "id": entry.id,
        "timestamp": entry.timestamp.isoformat(),
        "requester": entry.requester,
        "environment": entry.environment,
        "task": entry.task,
        "secret_ref": entry.secret_ref,
        "action": entry.action,
        "policy_name": entry.policy_name,
        "ttl_seconds": entry.ttl_seconds,
        "anomaly_score": entry.anomaly_score,
    })
    dead: list[Any] = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


async def get_logs(
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
    requester: str | None = None,
    environment: str | None = None,
) -> list[AuditLog]:
    async with async_session() as session:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if requester:
            stmt = stmt.where(AuditLog.requester == requester)
        if environment:
            stmt = stmt.where(AuditLog.environment == environment)
        stmt = stmt.offset(offset).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_stats() -> dict:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with async_session() as session:
        # Total today
        r = await session.execute(
            select(func.count(AuditLog.id)).where(AuditLog.timestamp >= start_of_day)
        )
        total_today = r.scalar() or 0

        # Denied today
        r = await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= start_of_day,
                AuditLog.action == "denied",
            )
        )
        denied_today = r.scalar() or 0

        # Active grants
        from backend.models import SecretGrant
        r = await session.execute(
            select(func.count(SecretGrant.id)).where(
                SecretGrant.revoked == False,
                SecretGrant.expires_at > now,
            )
        )
        active = r.scalar() or 0

        # Anomaly alerts today
        r = await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.timestamp >= start_of_day,
                AuditLog.anomaly_score > 0.5,
            )
        )
        anomalies = r.scalar() or 0

    return {
        "total_requests_today": total_today,
        "denied_requests_today": denied_today,
        "active_grants": active,
        "anomaly_alerts_today": anomalies,
    }
