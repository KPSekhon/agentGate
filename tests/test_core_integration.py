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
