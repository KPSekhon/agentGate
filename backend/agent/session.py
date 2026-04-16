from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from backend.audit.logger import log_event
from backend.database import async_session
from backend.models import SecretGrant
from backend.policy.engine import PolicyEngine
from backend.secrets.provider import SecretProvider


class AgentSessionManager:
    """Manages two-phase credential grants for AI agents.

    Phase 1: Agent requests a grant -> receives an opaque grant_id + metadata (no secret).
    Phase 2: Agent exchanges the grant_id -> receives the secret value (uses_remaining decremented).

    This ensures the secret is only delivered when the agent actively needs it,
    and each exchange is tracked and use-limited.
    """

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

        # --- Rate limiting ---
        rate_result = await self._check_rate_limit(requester, source_ip)
        if rate_result is not None:
            return rate_result

        # --- Policy evaluation ---
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
            if policy and policy.deny:
                reason = (
                    f"Explicitly denied by policy '{policy.name}'. "
                    f"This policy blocks {requester} in environment '{environment}'."
                )
            else:
                reason = (
                    f"No policy grants '{requester}' access to '{secret_ref}' "
                    f"in environment '{environment}' for task '{task}'. "
                    f"Define a policy with matching conditions and grants."
                )
            return {"error": "access_denied", "reason": reason}

        # Use the lesser of requested TTL and policy TTL
        ttl = min(requested_ttl, grant.ttl_seconds)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl)

        # Log the grant (Phase 1 -- no secret resolved yet)
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
        asyncio.create_task(
            self._expire_grant(grant_record.id, ttl, requester, environment, task, secret_ref)
        )

        # Phase 1 response: grant token + metadata, NO secret value
        return {
            "grant_id": grant_record.id,
            "expires_at": expires_at,
            "ttl_seconds": ttl,
            "uses_remaining": grant.max_uses,
            "policy": policy.name,
        }

    async def exchange_grant(self, grant_id: str, source_ip: str = "") -> dict:
        """Phase 2: Exchange a grant_id for the actual secret value.

        Decrements uses_remaining. When uses hit 0, the grant is auto-revoked.
        """
        async with async_session() as session:
            result = await session.execute(
                select(SecretGrant).where(SecretGrant.id == grant_id)
            )
            record = result.scalar_one_or_none()

            if not record:
                return {"error": "not_found", "reason": f"Grant '{grant_id}' does not exist."}
            if record.revoked:
                return {"error": "revoked", "reason": "This grant has been revoked."}
            expires = record.expires_at.replace(tzinfo=timezone.utc) if record.expires_at.tzinfo is None else record.expires_at
            if expires < datetime.now(timezone.utc):
                return {"error": "expired", "reason": "This grant has expired."}
            if record.uses_remaining <= 0:
                return {"error": "exhausted", "reason": "No remaining uses on this grant."}

            # Decrement uses
            record.uses_remaining -= 1
            if record.uses_remaining <= 0:
                record.revoked = True
            await session.commit()

        # Resolve the secret
        secret_value = await self.provider.resolve(record.secret_ref)

        await log_event(
            requester=record.requester,
            environment="",
            task="",
            secret_ref=record.secret_ref,
            action="exchanged",
            source_ip=source_ip,
        )

        return {
            "grant_id": grant_id,
            "secret_value": secret_value,
            "uses_remaining": record.uses_remaining,
        }

    async def release_grant(self, grant_id: str) -> dict:
        async with async_session() as session:
            result = await session.execute(
                select(SecretGrant).where(SecretGrant.id == grant_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                return {"error": "not_found", "reason": f"Grant '{grant_id}' does not exist."}
            if record.revoked:
                return {"error": "already_revoked", "reason": "Grant already revoked."}

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

    async def revoke_agent(self, agent_name: str) -> dict:
        """Revoke ALL active grants for an agent. Used for incident response."""
        requester = f"agent:{agent_name}"

        async with async_session() as session:
            # Select all non-revoked grants (skip expires_at comparison to avoid
            # timezone-naive vs timezone-aware issues with SQLite)
            result = await session.execute(
                select(SecretGrant).where(
                    SecretGrant.requester == requester,
                    SecretGrant.revoked == False,
                )
            )
            active_grants = list(result.scalars().all())

            if not active_grants:
                return {"status": "no_active_grants", "agent": agent_name, "revoked_count": 0}

            for grant in active_grants:
                grant.revoked = True
            await session.commit()

        # Log each revocation
        for grant in active_grants:
            await log_event(
                requester=requester,
                environment="",
                task="",
                secret_ref=grant.secret_ref,
                action="revoked",
            )

        return {
            "status": "revoked",
            "agent": agent_name,
            "revoked_count": len(active_grants),
        }

    async def _check_rate_limit(self, requester: str, source_ip: str) -> dict | None:
        """Per-agent rate limiting based on configured threshold."""
        from backend.config import settings
        from sqlalchemy import func
        limit = settings.rate_limit_per_minute
        # Use naive UTC to match SQLite's stored format (no timezone suffix)
        one_min_ago = datetime.utcnow() - timedelta(minutes=1)

        async with async_session() as session:
            from backend.models import AuditLog
            result = await session.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.requester == requester,
                    AuditLog.timestamp >= one_min_ago,
                )
            )
            count = result.scalar() or 0

        if count >= limit:
            await log_event(
                requester=requester,
                environment="",
                task="",
                secret_ref="",
                action="rate_limited",
                source_ip=source_ip,
            )
            return {
                "error": "rate_limited",
                "reason": f"Agent '{requester}' exceeded {limit} requests/minute. Wait before retrying.",
            }
        return None

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
