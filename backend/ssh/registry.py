from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from backend.audit.logger import log_event
from backend.database import async_session
from backend.models import SSHKey
from backend.policy.engine import PolicyEngine
from backend.secrets.provider import SecretProvider


class SSHKeyRegistry:
    def __init__(self, engine: PolicyEngine, provider: SecretProvider) -> None:
        self.engine = engine
        self.provider = provider

    async def list_keys(self) -> list[SSHKey]:
        async with async_session() as session:
            result = await session.execute(select(SSHKey).order_by(SSHKey.name))
            return list(result.scalars().all())

    async def register_key(
        self, name: str, fingerprint: str, key_type: str, has_passphrase: bool, description: str
    ) -> SSHKey:
        key = SSHKey(
            name=name,
            fingerprint=fingerprint,
            key_type=key_type,
            has_passphrase=has_passphrase,
            description=description,
        )
        async with async_session() as session:
            session.add(key)
            await session.commit()
            await session.refresh(key)
        return key

    async def request_key(
        self,
        requester: str,
        environment: str,
        task: str,
        key_name: str,
        source_ip: str = "",
    ) -> dict:
        secret_ref = f"ssh://{key_name}"
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

        private_key = await self.provider.resolve_ssh_key(key_name)

        # Update usage stats
        async with async_session() as session:
            result = await session.execute(select(SSHKey).where(SSHKey.name == key_name))
            key_record = result.scalar_one_or_none()
            if key_record:
                key_record.last_used_at = datetime.now(timezone.utc)
                key_record.last_used_by = requester
                key_record.access_count += 1

                # Passive check: flag unencrypted keys
                warning = None
                if not key_record.has_passphrase:
                    warning = "WARNING: This private key has no passphrase protection"

                await session.commit()

        await log_event(
            requester=requester,
            environment=environment,
            task=task,
            secret_ref=secret_ref,
            action="granted",
            policy_name=policy.name,
            ttl_seconds=grant.ttl_seconds,
            source_ip=source_ip,
        )

        result = {
            "key_name": key_name,
            "private_key": private_key,
            "ttl_seconds": grant.ttl_seconds,
            "policy": policy.name,
        }
        if warning:
            result["warning"] = warning
        return result
