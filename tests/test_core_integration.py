"""Integration test for the Python -> Rust core gRPC seam.

Requires the Rust core running on localhost:50051 with the real policies dir:
    agentgate serve --addr 127.0.0.1:50051 --policy-dir policies

Skipped automatically if the core is unreachable, so the normal pytest suite
(demo mode) is unaffected.
"""
from __future__ import annotations

import pytest

from backend.core_client import CoreClient

CORE_ADDR = "localhost:50051"


@pytest.fixture(scope="module")
def core():
    client = CoreClient(CORE_ADDR)
    if not client.health():
        client.close()
        pytest.skip(f"Rust core not running at {CORE_ADDR}")
    yield client
    client.close()


def test_core_allows_ci_deploy(core):
    grant, policy = core.evaluate(
        "agent:github-actions", "ci", "deploy", "op://ci-vault/deploy-key/credential"
    )
    assert grant is not None
    assert grant.ttl_seconds == 900
    assert grant.max_uses == 1
    assert policy.name == "ci-deploy-access"


def test_core_denies_ci_in_production(core):
    grant, policy = core.evaluate(
        "agent:github-actions", "production", "deploy", "op://prod-vault/db/credential"
    )
    assert grant is None
    assert policy.name == "ci-deny-production"


def test_core_denies_unknown_agent(core):
    grant, policy = core.evaluate(
        "agent:unknown", "staging", "test", "op://x/y/z"
    )
    assert grant is None
    assert policy.name == "default-deny-all"


def test_core_health(core):
    assert core.health() is True


def _claims(expires_at: int):
    import time

    return dict(
        grant_id="grant-test-001",
        requester="agent:deploy-bot",
        secret_ref="op://vault/api-key/credential",
        environment="staging",
        task="deploy",
        issued_at=int(time.time()),
        expires_at=expires_at,
        max_uses=1,
        policy_name="deploy-access",
    )


def test_core_mints_and_verifies_token(core):
    import time

    token = core.mint_token(**_claims(int(time.time()) + 300))
    assert token.startswith("ag2.")  # Ed25519 public-key scheme

    claims, reason = core.verify_token(token)
    assert reason == ""
    assert claims is not None
    assert claims["grant_id"] == "grant-test-001"
    assert claims["requester"] == "agent:deploy-bot"
    assert claims["max_uses"] == 1
    # The core stamps its signing key id into every token.
    assert claims["key_id"]


def test_core_publishes_public_key(core):
    pk = core.public_key()
    assert pk["algorithm"] == "Ed25519"
    assert pk["key_id"]
    # Ed25519 public keys are 32 bytes => 64 hex chars.
    assert len(pk["public_key"]) == 64

    # The key id embedded in a freshly minted token matches the published key.
    import time

    token = core.mint_token(**_claims(int(time.time()) + 300))
    claims, _ = core.verify_token(token)
    assert claims["key_id"] == pk["key_id"]


def test_core_rejects_tampered_token(core):
    import time

    token = core.mint_token(**_claims(int(time.time()) + 300))
    prefix, payload_hex, sig_hex = token.split(".", 2)
    sig = bytearray(bytes.fromhex(sig_hex))
    sig[0] ^= 0xFF  # flip bits in the signature
    tampered = f"{prefix}.{payload_hex}.{sig.hex()}"

    claims, reason = core.verify_token(tampered)
    assert claims is None
    assert reason  # non-empty rejection reason


def test_core_rejects_expired_token(core):
    import time

    # expires one hour in the past
    token = core.mint_token(**_claims(int(time.time()) - 3600))
    claims, reason = core.verify_token(token)
    assert claims is None
    assert "expired" in reason.lower()
