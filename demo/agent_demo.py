#!/usr/bin/env python3
"""
AgentGate Demo — AI Agent Credential Broker Flow

This script demonstrates:
1. Requesting a secret through the AgentGate API (granted)
2. Using the secret (masked output)
3. Releasing the secret
4. Requesting a denied secret
5. Triggering anomaly detection with rapid requests

Usage:
    # Start the server first:
    agentgate server start
    # Then run:
    python demo/agent_demo.py
"""

import httpx
import time
import sys

BASE_URL = "http://localhost:8000"
TOKEN = "demo-token-12345"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    print("AgentGate Demo — AI Agent Credential Broker")
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

    # --- Step 1: Request a secret (should be GRANTED) ---
    section("Step 1: Request an API key (expect: GRANTED)")

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
        masked = data["secret_value"][:8] + "..." + data["secret_value"][-4:]
        print(f"\n  ✓ GRANTED")
        print(f"    grant_id:  {data['grant_id']}")
        print(f"    secret:    {masked} (masked)")
        print(f"    expires:   {data['expires_at']}")
        print(f"    policy:    {data['policy']}")
        grant_id = data["grant_id"]
    else:
        print(f"\n  ✗ Unexpected: {r.status_code} — {r.text}")
        grant_id = None

    # --- Step 2: Release the secret ---
    section("Step 2: Release the secret")

    if grant_id:
        r = httpx.post(
            f"{BASE_URL}/agent/release",
            json={"grant_id": grant_id},
            headers=HEADERS,
        )
        print(f"  ✓ {r.json()}")

    # --- Step 3: Request a denied secret ---
    section("Step 3: Request a production secret (expect: DENIED)")

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
        print(f"\n  ✓ DENIED (as expected)")
        print(f"    reason: {detail.get('reason', 'No matching policy')}")
    else:
        print(f"\n  ✗ Unexpected: {r.status_code} — {r.text}")

    # --- Step 4: Trigger anomaly detection ---
    section("Step 4: Rapid requests to trigger anomaly detection")

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
        status = "granted" if r.status_code == 200 else "denied"
        print(f"    [{i+1:2d}] {status}", end="")
        if r.status_code == 200:
            # Release immediately
            gid = r.json()["grant_id"]
            httpx.post(f"{BASE_URL}/agent/release", json={"grant_id": gid}, headers=HEADERS)
        print()

    # --- Step 5: Check audit stats ---
    section("Step 5: Check audit stats")

    r = httpx.get(f"{BASE_URL}/audit/stats")
    stats = r.json()
    print(f"  Total requests today:   {stats['total_requests_today']}")
    print(f"  Denied requests today:  {stats['denied_requests_today']}")
    print(f"  Active grants:          {stats['active_grants']}")
    print(f"  Anomaly alerts today:   {stats['anomaly_alerts_today']}")

    # --- Step 6: Show recent logs ---
    section("Step 6: Recent audit logs")

    r = httpx.get(f"{BASE_URL}/audit/logs", params={"limit": 5})
    for entry in r.json():
        score = entry["anomaly_score"]
        flag = " ⚠️ ANOMALY" if score > 0.5 else ""
        print(f"  [{entry['timestamp'][:19]}] {entry['action']:>8s} | {entry['requester']:20s} | {entry['secret_ref']}{flag}")

    print(f"\n{'='*60}")
    print("  Demo complete. Check the dashboard at http://localhost:3000")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
