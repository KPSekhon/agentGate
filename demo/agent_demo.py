#!/usr/bin/env python3
"""
AgentGate Demo -- AI Agent Two-Phase Credential Broker Flow

This script demonstrates:
1. Phase 1: Requesting a credential grant (receives grant_id, NOT the secret)
2. Phase 2: Exchanging the grant_id for the actual secret
3. Releasing the grant when done
4. A denied request (wrong environment)
5. Bulk revocation of an agent's grants
6. Rate limiting (rapid-fire requests)
7. Anomaly detection

Usage:
    # Start the server first:
    agentgate server start
    # Then run:
    python demo/agent_demo.py
"""

import httpx
import sys

BASE_URL = "http://localhost:8000"
TOKEN = "demo-token-12345"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    print("AgentGate Demo -- Two-Phase Credential Broker")
    print("=" * 60)

    # Check server is running
    try:
        r = httpx.get(f"{BASE_URL}/")
        info = r.json()
        print(f"Connected to AgentGate v{info['version']} (mode: {info['mode']})")
    except httpx.ConnectError:
        print("ERROR: AgentGate server is not running.")
        print("Start it with: agentgate server start")
        sys.exit(1)

    # --- Step 1: Phase 1 -- Request a grant (no secret returned) ---
    section("Step 1: Request a grant (Phase 1 -- no secret in response)")

    payload = {
        "agent_name": "demo-agent-01",
        "environment": "development",
        "task": "summarize-logs",
        "secret_ref": "op://demo-vault/api-key/credential",
        "requested_ttl": 300,
    }
    print(f"POST /agent/request-secret")
    print(f"  agent:  {payload['agent_name']}")
    print(f"  env:    {payload['environment']}")
    print(f"  task:   {payload['task']}")
    print(f"  secret: {payload['secret_ref']}")

    r = httpx.post(f"{BASE_URL}/agent/request-secret", json=payload, headers=HEADERS)

    if r.status_code == 200:
        data = r.json()
        print(f"\n  [GRANTED] Grant issued -- but NO secret in response!")
        print(f"    grant_id:       {data['grant_id']}")
        print(f"    expires_at:     {data['expires_at']}")
        print(f"    uses_remaining: {data['uses_remaining']}")
        print(f"    policy:         {data['policy']}")
        print(f"    secret_value:   <not present -- that's the point>")
        grant_id = data["grant_id"]
    else:
        print(f"\n  [ERROR] Unexpected: {r.status_code} -- {r.text}")
        grant_id = None

    # --- Step 2: Phase 2 -- Exchange the grant for the actual secret ---
    section("Step 2: Exchange grant for secret (Phase 2)")

    if grant_id:
        r = httpx.post(
            f"{BASE_URL}/agent/exchange",
            json={"grant_id": grant_id},
            headers=HEADERS,
        )
        if r.status_code == 200:
            data = r.json()
            masked = data["secret_value"][:8] + "..." + data["secret_value"][-4:]
            print(f"  [SECRET] Now we have the secret:")
            print(f"    grant_id:       {data['grant_id']}")
            print(f"    secret_value:   {masked} (masked)")
            print(f"    uses_remaining: {data['uses_remaining']}")
        else:
            print(f"  [ERROR] {r.status_code}: {r.text}")

    # --- Step 3: Try to exchange again (should fail -- uses exhausted) ---
    section("Step 3: Try exchanging again (expect: exhausted)")

    if grant_id:
        r = httpx.post(
            f"{BASE_URL}/agent/exchange",
            json={"grant_id": grant_id},
            headers=HEADERS,
        )
        if r.status_code == 410:
            detail = r.json().get("detail", {})
            print(f"  [BLOCKED] {detail.get('error')}: {detail.get('reason')}")
            print(f"    The grant was single-use. Secret is no longer available.")
        else:
            print(f"  Unexpected: {r.status_code} -- {r.text}")

    # --- Step 4: Request a denied secret ---
    section("Step 4: Request a production secret (expect: DENIED)")

    payload_denied = {
        "agent_name": "demo-agent-01",
        "environment": "production",
        "task": "deploy",
        "secret_ref": "op://prod-vault/deploy-key/credential",
        "requested_ttl": 60,
    }
    print(f"POST /agent/request-secret")
    print(f"  agent:  {payload_denied['agent_name']}")
    print(f"  env:    {payload_denied['environment']}")
    print(f"  secret: {payload_denied['secret_ref']}")

    r = httpx.post(f"{BASE_URL}/agent/request-secret", json=payload_denied, headers=HEADERS)

    if r.status_code == 403:
        detail = r.json().get("detail", {})
        print(f"\n  [DENIED] {detail.get('reason', 'No matching policy')}")
    else:
        print(f"\n  Unexpected: {r.status_code} -- {r.text}")

    # --- Step 5: Bulk revocation ---
    section("Step 5: Bulk revoke all grants for an agent")

    # First, create a few grants
    for i in range(3):
        httpx.post(f"{BASE_URL}/agent/request-secret", json={
            "agent_name": "demo-rogue",
            "environment": "development",
            "task": f"task-{i}",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 600,
        }, headers=HEADERS)

    print("  Created 3 grants for 'rogue-agent'")

    r = httpx.post(
        f"{BASE_URL}/agent/revoke-agent",
        json={"agent_name": "demo-rogue"},
        headers=HEADERS,
    )
    data = r.json()
    print(f"  [REVOKED] {data.get('revoked_count', 0)} grants revoked for '{data.get('agent', 'rogue-agent')}'")

    # --- Step 6: Rapid requests to trigger anomaly detection ---
    section("Step 6: Rapid requests (anomaly detection + rate limiting)")

    print("  Sending 12 rapid requests...")
    for i in range(12):
        payload_rapid = {
            "agent_name": "demo-agent-01",
            "environment": "development",
            "task": "batch-process",
            "secret_ref": "op://demo-vault/api-key/credential",
            "requested_ttl": 60,
        }
        r = httpx.post(f"{BASE_URL}/agent/request-secret", json=payload_rapid, headers=HEADERS)
        if r.status_code == 200:
            status = "granted"
        elif r.status_code == 429:
            status = "RATE LIMITED"
        else:
            status = f"denied ({r.status_code})"
        print(f"    [{i+1:2d}] {status}")

    # --- Step 7: Check audit stats ---
    section("Step 7: Audit stats")

    r = httpx.get(f"{BASE_URL}/audit/stats")
    stats = r.json()
    print(f"  Total requests today:   {stats['total_requests_today']}")
    print(f"  Denied requests today:  {stats['denied_requests_today']}")
    print(f"  Active grants:          {stats['active_grants']}")
    print(f"  Anomaly alerts today:   {stats['anomaly_alerts_today']}")

    # --- Step 8: Show recent logs ---
    section("Step 8: Recent audit logs")

    r = httpx.get(f"{BASE_URL}/audit/logs", params={"limit": 8})
    for entry in r.json():
        score = entry["anomaly_score"]
        flag = " << ANOMALY" if score > 0.5 else ""
        print(f"  [{entry['timestamp'][:19]}] {entry['action']:>12s} | {entry['requester']:25s} | {entry['secret_ref']}{flag}")

    print(f"\n{'='*60}")
    print("  Demo complete. Check the dashboard at http://localhost:3000")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
