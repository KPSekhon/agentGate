from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from backend.database import async_session
from backend.models import AuditLog


async def compute_anomaly_score(requester: str, environment: str) -> float:
    """Score 0.0–1.0 based on three heuristics."""
    score = 0.0
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        # 1. Frequency spike — >10 requests in the last 5 minutes
        five_min_ago = now - timedelta(minutes=5)
        r = await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.requester == requester,
                AuditLog.timestamp >= five_min_ago,
            )
        )
        recent_count = r.scalar() or 0
        if recent_count > 10:
            score += 0.4

        # 2. Off-hours access to production
        hour = now.hour
        if environment == "production" and (hour < 6 or hour > 22):
            score += 0.3

        # 3. New requester — first time ever
        r = await session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.requester == requester,
            )
        )
        total = r.scalar() or 0
        if total == 0:
            score += 0.3

    return min(score, 1.0)
