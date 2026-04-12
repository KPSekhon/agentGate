"""Tests for anomaly detection heuristics."""
from __future__ import annotations

import pytest

from backend.audit.anomaly import compute_anomaly_score


@pytest.mark.asyncio
async def test_new_requester_flagged():
    """First-ever request from a requester should get a 0.3 score."""
    score = await compute_anomaly_score("agent:brand-new", "development")
    assert score >= 0.3


@pytest.mark.asyncio
async def test_known_requester_lower_score():
    """After inserting a prior log entry, the new-requester flag should not trigger."""
    from backend.models import AuditLog
    from backend.database import async_session

    async with async_session() as session:
        entry = AuditLog(
            requester="agent:known-agent",
            environment="development",
            task="test",
            secret_ref="op://test/key/cred",
            action="granted",
        )
        session.add(entry)
        await session.commit()

    score = await compute_anomaly_score("agent:known-agent", "development")
    assert score < 0.3
