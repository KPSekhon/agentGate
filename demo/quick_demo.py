#!/usr/bin/env python3
"""
AgentGate 60-Second Demo
========================
Optimized for screen recording. Shows the core value prop in under a minute.

Prerequisites: agentgate server running (agentgate server)
"""

import httpx
import sys
import time

URL = "http://localhost:8000"
H = {"Authorization": "Bearer demo-token-12345", "Content-Type": "application/json"}

def pause(s=1.5):
    time.sleep(s)

def header(text):
    print(f"\n  {'='*50}")
    print(f"  {text}")
    print(f"  {'='*50}\n")

def main():
    # --- Intro ---
    print("\n  AgentGate -- Runtime Credential Broker")
    print("  ======================================")
    print("  Scoped, time-limited secrets for AI agents.\n")
    pause(2)

    try:
        r = httpx.get(f"{URL}/")
        print(f"  Server: v{r.json()['version']} (mode: {r.json()['mode']})")
    except httpx.ConnectError:
        print("  ERROR: Start server first -> agentgate server")
        sys.exit(1)
    pause()

    # --- 1. Two-Phase Grant ---
    header("PHASE 1: Request a grant (no secret returned)")

    print("  POST /agent/request-secret")
    print("    agent: demo-agent-01")
    print("    env:   development")
    print("    ref:   op://demo-vault/api-key/credential")
    pause()

    r = httpx.post(f"{URL}/agent/request-secret", json={
        "agent_name": "demo-agent-01",
        "environment": "development",
        "task": "summarize-logs",
        "secret_ref": "op://demo-vault/api-key/credential",
        "requested_ttl": 300,
    }, headers=H)
    data = r.json()
    gid = data["grant_id"]

    print(f"\n  GRANTED -- but look, no secret in the response:")
    print(f"    grant_id:       {gid}")
    print(f"    uses_remaining: {data['uses_remaining']}")
    print(f"    policy:         {data['policy']}")
    print(f"    secret_value:   << NOT HERE >>")
    pause(2)

    # --- 2. Exchange ---
    header("PHASE 2: Exchange grant for the actual secret")

    print("  POST /agent/exchange")
    print(f"    grant_id: {gid}")
    pause()

    r = httpx.post(f"{URL}/agent/exchange", json={"grant_id": gid}, headers=H)
    data = r.json()
    masked = data["secret_value"][:10] + "..." + data["secret_value"][-4:]

    print(f"\n  SECRET DELIVERED:")
    print(f"    value:          {masked}")
    print(f"    uses_remaining: {data['uses_remaining']}  (grant is now spent)")
    pause(2)

    # --- 3. Exhausted ---
    header("USED UP: Try exchanging again")

    r = httpx.post(f"{URL}/agent/exchange", json={"grant_id": gid}, headers=H)
    detail = r.json().get("detail", {})
    print(f"  HTTP {r.status_code}: {detail.get('error', '?')} -- {detail.get('reason', '?')}")
    print(f"  Single-use grant. Secret is gone.")
    pause(2)

    # --- 4. Denied ---
    header("DENIED: Production access blocked by policy")

    r = httpx.post(f"{URL}/agent/request-secret", json={
        "agent_name": "demo-agent-01",
        "environment": "production",
        "task": "deploy",
        "secret_ref": "op://prod/deploy-key/cred",
        "requested_ttl": 60,
    }, headers=H)
    detail = r.json().get("detail", {})
    print(f"  HTTP 403: {detail.get('reason', 'Denied')}")
    pause(2)

    # --- 5. Bulk Revoke ---
    header("INCIDENT RESPONSE: Revoke all grants for an agent")

    for i in range(3):
        httpx.post(f"{URL}/agent/request-secret", json={
            "agent_name": "demo-compromised",
            "environment": "development",
            "task": f"task-{i}",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 600,
        }, headers=H)
    print("  Created 3 active grants for 'demo-compromised'")
    pause()

    r = httpx.post(f"{URL}/agent/revoke-agent", json={"agent_name": "demo-compromised"}, headers=H)
    data = r.json()
    print(f"  REVOKED: {data['revoked_count']} grants killed instantly")
    pause(2)

    # --- 6. Audit ---
    header("AUDIT: Full trail of every action")

    r = httpx.get(f"{URL}/audit/stats")
    s = r.json()
    print(f"  Requests today:  {s['total_requests_today']}")
    print(f"  Denied:          {s['denied_requests_today']}")
    print(f"  Active grants:   {s['active_grants']}")
    pause()

    r = httpx.get(f"{URL}/audit/logs", params={"limit": 5})
    print(f"\n  Latest audit entries:")
    for e in r.json():
        print(f"    {e['action']:>12s} | {e['requester']:25s} | {e['secret_ref'][:35]}")
    pause(2)

    # --- End ---
    print(f"\n  {'='*50}")
    print("  AgentGate: policy-scoped, time-limited, audited.")
    print("  Dashboard: http://localhost:3000")
    print(f"  {'='*50}\n")


if __name__ == "__main__":
    main()
