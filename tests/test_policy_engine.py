from __future__ import annotations

from pathlib import Path

from backend.policy.engine import PolicyEngine


def test_deny_by_default(policy_dir):
    engine = PolicyEngine(policy_dir)
    grant, policy = engine.evaluate("agent:unknown", "production", "hack", "op://secret/thing/cred")
    assert grant is None


def test_demo_agent_granted(policy_dir):
    engine = PolicyEngine(policy_dir)
    grant, policy = engine.evaluate(
        "agent:demo-agent-01", "development", "summarize", "op://demo-vault/api-key/credential"
    )
    assert grant is not None
    assert policy.name == "demo-agent-access"
    assert grant.ttl_seconds == 300


def test_ci_denied_production(policy_dir):
    engine = PolicyEngine(policy_dir)
    grant, policy = engine.evaluate(
        "agent:github-actions", "production", "deploy", "op://ci-vault/deploy-key/credential"
    )
    assert grant is None
    assert policy is not None
    assert policy.deny is True


def test_ci_granted_in_ci_env(policy_dir):
    engine = PolicyEngine(policy_dir)
    grant, policy = engine.evaluate(
        "agent:github-actions", "ci", "deploy", "op://ci-vault/deploy-key/credential"
    )
    assert grant is not None
    assert grant.ttl_seconds == 900


def test_evaluate_all_grants(policy_dir):
    engine = PolicyEngine(policy_dir)
    grants = engine.evaluate_all_grants("agent:demo-agent-01", "development", "any-task")
    assert len(grants) >= 2  # at least api-key and db-password
