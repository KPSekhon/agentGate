"""Integration tests for the Agent REST API (two-phase grant flow)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.agent.routes import set_session_manager
from backend.agent.session import AgentSessionManager
from backend.main import app
from backend.policy.engine import PolicyEngine
from backend.secrets.mock import MockSecretProvider
from backend.ssh.registry import SSHKeyRegistry
from backend.ssh.routes import set_ssh_registry


@pytest.fixture(autouse=True)
def _setup_app():
    """Initialize the app components that lifespan normally handles."""
    policy_engine = PolicyEngine("./policies")
    provider = MockSecretProvider()

    manager = AgentSessionManager(policy_engine, provider)
    set_session_manager(manager)

    registry = SSHKeyRegistry(policy_engine, provider)
    set_ssh_registry(registry)


HEADERS = {"Authorization": "Bearer demo-token-12345"}


# --- Phase 1: Request Grant ---

@pytest.mark.asyncio
async def test_phase1_grant_returns_no_secret():
    """Phase 1 should return grant_id and metadata, but NOT the secret value."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/request-secret", json={
            "agent_name": "demo-agent-01",
            "environment": "development",
            "task": "test-task",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 60,
        }, headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert "grant_id" in data
        assert "expires_at" in data
        assert "uses_remaining" in data
        assert data["policy"] == "demo-agent-access"
        # The key assertion: no secret in Phase 1
        assert "secret_value" not in data


# --- Phase 2: Exchange Grant ---

@pytest.mark.asyncio
async def test_phase2_exchange_returns_secret():
    """Phase 2 should return the actual secret when exchanging a valid grant."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Phase 1
        r = await client.post("/agent/request-secret", json={
            "agent_name": "demo-agent-01",
            "environment": "development",
            "task": "test",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 60,
        }, headers=HEADERS)
        grant_id = r.json()["grant_id"]

        # Phase 2
        r = await client.post("/agent/exchange", json={
            "grant_id": grant_id,
        }, headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["secret_value"].startswith("demo-api-key-")
        assert data["grant_id"] == grant_id


@pytest.mark.asyncio
async def test_phase2_exchange_exhausted_after_max_uses():
    """A single-use grant should fail on the second exchange attempt."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/request-secret", json={
            "agent_name": "demo-agent-01",
            "environment": "development",
            "task": "test",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 60,
        }, headers=HEADERS)
        grant_id = r.json()["grant_id"]

        # First exchange: OK
        r = await client.post("/agent/exchange", json={"grant_id": grant_id}, headers=HEADERS)
        assert r.status_code == 200

        # Second exchange: should be exhausted/revoked
        r = await client.post("/agent/exchange", json={"grant_id": grant_id}, headers=HEADERS)
        assert r.status_code == 410


@pytest.mark.asyncio
async def test_exchange_nonexistent_grant():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/exchange", json={
            "grant_id": "nonexistent-id",
        }, headers=HEADERS)
        assert r.status_code == 404


# --- Deny Scenarios ---

@pytest.mark.asyncio
async def test_request_denied_no_policy():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/request-secret", json={
            "agent_name": "unknown-agent",
            "environment": "production",
            "task": "hack",
            "secret_ref": "op://prod/secret/cred",
            "requested_ttl": 60,
        }, headers=HEADERS)
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert detail["error"] == "access_denied"
        # Error message should explain what went wrong
        assert len(detail["reason"]) > 20  # not a vague one-liner


@pytest.mark.asyncio
async def test_request_denied_explicit_deny():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/request-secret", json={
            "agent_name": "github-actions",
            "environment": "production",
            "task": "deploy",
            "secret_ref": "op://ci-vault/deploy-key/credential",
            "requested_ttl": 60,
        }, headers=HEADERS)
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert "denied" in detail["reason"].lower() or "blocks" in detail["reason"].lower()


# --- Release ---

@pytest.mark.asyncio
async def test_release_grant():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/request-secret", json={
            "agent_name": "demo-agent-01",
            "environment": "development",
            "task": "test",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 300,
        }, headers=HEADERS)
        grant_id = r.json()["grant_id"]

        r = await client.post("/agent/release", json={"grant_id": grant_id}, headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["status"] == "released"

        # Exchange after release should fail
        r = await client.post("/agent/exchange", json={"grant_id": grant_id}, headers=HEADERS)
        assert r.status_code == 410


@pytest.mark.asyncio
async def test_release_nonexistent_grant():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/release", json={"grant_id": "nope"}, headers=HEADERS)
        assert r.status_code == 404


# --- Bulk Revocation ---

@pytest.mark.asyncio
async def test_revoke_agent_all_grants():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create 3 grants (agent name must match demo-* pattern)
        grant_ids = []
        for i in range(3):
            r = await client.post("/agent/request-secret", json={
                "agent_name": "demo-rogue",
                "environment": "development",
                "task": f"task-{i}",
                "secret_ref": "op://demo-vault/api-key/credential",
                "requested_ttl": 600,
            }, headers=HEADERS)
            assert r.status_code == 200, f"Grant {i} failed: {r.text}"
            grant_ids.append(r.json()["grant_id"])

        # Revoke all
        r = await client.post("/agent/revoke-agent", json={
            "agent_name": "demo-rogue",
        }, headers=HEADERS)
        assert r.status_code == 200
        data = r.json()
        assert data["revoked_count"] == 3

        # All grants should now be unusable
        for gid in grant_ids:
            r = await client.post("/agent/exchange", json={"grant_id": gid}, headers=HEADERS)
            assert r.status_code == 410


# --- Rate Limiting ---

@pytest.mark.asyncio
async def test_rate_limiting_rejects_excess_requests():
    """Seed the audit log with 30 entries, then the 31st request should be rate-limited."""
    from backend.models import AuditLog
    from backend.database import async_session
    from datetime import datetime, timezone

    # Seed 30 audit entries for agent:demo-flood to simulate a burst
    async with async_session() as session:
        for i in range(30):
            entry = AuditLog(
                requester="agent:demo-flood",
                environment="development",
                task="flood",
                secret_ref="op://demo-vault/api-key/credential",
                action="granted",
                timestamp=datetime.now(timezone.utc),
            )
            session.add(entry)
        await session.commit()

    # Now the next request from this agent should be rate-limited
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/request-secret", json={
            "agent_name": "demo-flood",
            "environment": "development",
            "task": "one-more",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 60,
        }, headers=HEADERS)
        assert r.status_code == 429
        detail = r.json()["detail"]
        assert detail["error"] == "rate_limited"


# --- Auth ---

@pytest.mark.asyncio
async def test_bad_auth_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/agent/request-secret", json={
            "agent_name": "demo-agent-01",
            "environment": "development",
            "task": "test",
            "secret_ref": "op://demo-vault/api-key/credential",
        }, headers={"Authorization": "Bearer wrong-token"})
        assert r.status_code == 403


# --- Audit ---

@pytest.mark.asyncio
async def test_audit_logs_populated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/agent/request-secret", json={
            "agent_name": "demo-agent-01",
            "environment": "development",
            "task": "audit-test",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 60,
        }, headers=HEADERS)

        r = await client.get("/audit/logs")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        assert logs[0]["requester"] == "agent:demo-agent-01"
        assert logs[0]["action"] == "granted"


@pytest.mark.asyncio
async def test_audit_stats():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/audit/stats")
        assert r.status_code == 200
        stats = r.json()
        assert "total_requests_today" in stats
        assert "active_grants" in stats


# --- Policies & SSH ---

@pytest.mark.asyncio
async def test_policies_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/policies")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_ssh_keys_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/ssh/keys")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_ssh_key_register_and_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/ssh/keys", json={
            "name": "test-deploy-key",
            "fingerprint": "SHA256:abcdef1234567890",
            "key_type": "ed25519",
            "has_passphrase": True,
            "description": "Test deploy key",
        })
        assert r.status_code == 200
        assert r.json()["name"] == "test-deploy-key"

        r = await client.get("/ssh/keys")
        keys = r.json()
        assert any(k["name"] == "test-deploy-key" for k in keys)
