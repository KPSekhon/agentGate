from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from backend.audit.logger import log_event
from backend.database import async_session
from backend.models import SecretGrant
from backend.policy.engine import PolicyEngine
from backend.secrets.provider import SecretProvider


class AgentSessionManager:
    def __init__(self, engine: PolicyEngine, provider: SecretProvider) -> None:
        self.engine = engine
        self.provider = provider

    async def request_grant(
        self,
        agent_name: str,
        environment: str,
        task: str,
        secret_ref: str,
        requested_ttl: int = 300,
        source_ip: str = "",
    ) -> dict:
        requester = f"agent:{agent_name}"

        grant, policy = self.engine.evaluate(requester, environment, task, secret_ref)

        if grant is None:
            await log_event(
                requester=requester,
                environment=environment,
                task=task,
                secret_ref=secret_ref,
                action="denied",
                policy_name=policy.name if policy else "no-match",
                source_ip=source_ip,
            )
            reason = f"Denied by policy '{policy.name}'" if policy else "No matching policy"
            return {"error": "access_denied", "reason": reason}

        # Use the lesser of requested TTL and policy TTL
        ttl = min(requested_ttl, grant.ttl_seconds)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl)

        # Resolve the actual secret
        secret_value = await self.provider.resolve(secret_ref)

        # Log the grant
        audit_entry = await log_event(
            requester=requester,
            environment=environment,
            task=task,
            secret_ref=secret_ref,
            action="granted",
            policy_name=policy.name,
            ttl_seconds=ttl,
            source_ip=source_ip,
        )

        # Create the grant record
        grant_record = SecretGrant(
            audit_log_id=audit_entry.id,
            requester=requester,
            secret_ref=secret_ref,
            granted_at=now,
            expires_at=expires_at,
            uses_remaining=grant.max_uses,
        )
        async with async_session() as session:
            session.add(grant_record)
            await session.commit()
            await session.refresh(grant_record)

        # Schedule auto-expiry
        asyncio.create_task(self._expire_grant(grant_record.id, ttl, requester, environment, task, secret_ref))

        return {
            "grant_id": grant_record.id,
            "secret_value": secret_value,
            "expires_at": expires_at,
            "ttl_seconds": ttl,
            "policy": policy.name,
        }

    async def release_grant(self, grant_id: str) -> dict:
        async with async_session() as session:
            result = await session.execute(
                select(SecretGrant).where(SecretGrant.id == grant_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                return {"error": "not_found", "reason": "Grant not found"}
            if record.revoked:
                return {"error": "already_revoked", "reason": "Grant already revoked"}

            record.revoked = True
            await session.commit()

        await log_event(
            requester=record.requester,
            environment="",
            task="",
            secret_ref=record.secret_ref,
            action="released",
        )
        return {"status": "released", "grant_id": grant_id}

    async def _expire_grant(
        self,
        grant_id: str,
        ttl: int,
        requester: str,
        environment: str,
        task: str,
        secret_ref: str,
    ) -> None:
        await asyncio.sleep(ttl)
        async with async_session() as session:
            result = await session.execute(
                select(SecretGrant).where(SecretGrant.id == grant_id)
            )
            record = result.scalar_one_or_none()
            if record and not record.revoked:
                record.revoked = True
                await session.commit()
                await log_event(
                    requester=requester,
                    environment=environment,
                    task=task,
                    secret_ref=secret_ref,
                    action="expired",
                )
