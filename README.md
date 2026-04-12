# AgentGate

**Runtime Credential Broker for AI Agents and Developer Workflows**

AgentGate gives AI agents, scripts, and CI pipelines scoped, time-limited access to secrets -- with policy enforcement, zero plaintext exposure, and full audit trails. Built on the 1Password SDK.

---

## The Problem

Modern developer workflows have a secret sprawl problem. Credentials live in `.env` files checked into repos, pasted into CI configs, embedded in LLM prompts, and shared over Slack. AI agents make this worse: they need credentials to be useful, but giving an agent unrestricted access to secrets is a governance disaster waiting to happen.

AgentGate solves this by acting as a **credential broker** -- agents and scripts request access for a specific task, get a time-scoped grant, and never see the raw secret in plaintext storage. Every request is evaluated against a YAML policy, every grant has a TTL, and every action is logged.

## Architecture

```
                         Two-Phase Grant Flow
                         ====================

 AI Agent                   AgentGate                     1Password SDK
 --------                   ---------                     -------------
    |                           |                              |
    |-- Phase 1: Request ------>|                              |
    |   (agent, env, task, ref) |-- Evaluate policy            |
    |                           |-- Check rate limit           |
    |                           |-- Log "granted"              |
    |<-- grant_id + metadata ---|   (no secret returned)       |
    |                           |                              |
    |-- Phase 2: Exchange ----->|                              |
    |   (grant_id)              |-- Validate grant             |
    |                           |-- Decrement uses ----------->|-- Resolve secret
    |                           |<-----------------------------|
    |<-- secret_value ----------|                              |
    |                           |-- Log "exchanged"            |
    |                           |                              |
    |-- Release --------------->|                              |
    |   (grant_id)              |-- Revoke grant               |
    |                           |-- Log "released"             |
```

The secret is never returned during the grant request. It's only delivered during an explicit exchange, which is tracked, use-limited, and auto-revoked.

## Features

### 1. Policy-Based Secret Access

YAML policies define who can request what, under which conditions. Deny by default -- if no policy matches, the request is refused and logged.

```yaml
# policies/demo-agent.yaml
name: demo-agent-access
description: "Allow demo agents to read demo secrets in development"
priority: 10
conditions:
  - requester: "agent:demo-*"
    environment: "development"
    task: "*"
grants:
  - secret_ref: "op://demo-vault/api-key/credential"
    ttl_seconds: 300
    max_uses: 1
deny: false
```

The policy engine checks five things before issuing any grant: **requester identity**, **requested secret**, **current environment**, **task context**, and **TTL window validity**.

### 2. Two-Phase Credential Grant (Agent API)

Unlike a simple secret fetch, AgentGate uses a two-phase flow that separates authorization from secret delivery:

**Phase 1 -- Request a grant** (no secret returned):
```bash
curl -X POST http://localhost:8000/agent/request-secret \
  -H "Authorization: Bearer demo-token-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "docs-agent",
    "task": "summarize-logs",
    "secret_ref": "op://demo-vault/openai-key/credential",
    "environment": "development",
    "requested_ttl": 1800
  }'
```
```json
{
  "grant_id": "a1b2c3d4-...",
  "expires_at": "2026-04-05T17:05:00Z",
  "ttl_seconds": 300,
  "uses_remaining": 1,
  "policy": "demo-agent-access"
}
```

**Phase 2 -- Exchange grant for secret:**
```bash
curl -X POST http://localhost:8000/agent/exchange \
  -H "Authorization: Bearer demo-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"grant_id": "a1b2c3d4-..."}'
```
```json
{
  "grant_id": "a1b2c3d4-...",
  "secret_value": "demo-openai-key-...",
  "uses_remaining": 0
}
```

Each exchange decrements `uses_remaining`. When exhausted, the grant is auto-revoked. Grants also auto-expire via background tasks.

### 3. Runtime Injection (CLI)

A thin CLI wrapper that fetches secrets at runtime, injects them into a subprocess, and clears them after exit. The secret never touches disk, never appears in shell history, and never exists outside the subprocess lifetime.

```bash
# Auto-discover secrets from policies
agentgate run --task deploy --env staging -- ./deploy.sh

# Explicit secret-to-env-var mapping
agentgate run --task deploy \
  --secret "op://vault/api-key/cred=OPENAI_API_KEY" \
  --secret "op://vault/db/pass=DATABASE_PASSWORD" \
  -- ./deploy.sh

# Or use a .agentgate.yaml project config (see below)
agentgate run -- ./deploy.sh
```

This mirrors exactly what `op run` and `op inject` do in 1Password's CLI, with a policy enforcement layer on top.

### 4. Project Configuration (`.agentgate.yaml`)

Projects can declare their secret requirements in a `.agentgate.yaml` file:

```yaml
environment: staging
task: deploy
secrets:
  - ref: "op://prod-vault/openai/api-key"
    env_var: "OPENAI_API_KEY"
  - ref: "op://prod-vault/database/password"
    env_var: "DATABASE_PASSWORD"
  - ref: "op://prod-vault/github/token"
    env_var: "GH_TOKEN"
```

When `agentgate run` finds this file (searches up the directory tree), it uses these mappings instead of requiring manual `--secret` flags. This solves the practical problem of scripts expecting specific env var names like `OPENAI_API_KEY` instead of auto-generated names from the `op://` path.

### 5. Rate Limiting

Per-agent rate limiting (30 requests/minute by default, configurable) prevents credential API abuse. When an agent exceeds the limit, requests are rejected with HTTP 429 and the event is logged for audit.

### 6. Bulk Revocation

If an agent is compromised, revoke all its active grants instantly:

```bash
curl -X POST http://localhost:8000/agent/revoke-agent \
  -H "Authorization: Bearer demo-token-12345" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "compromised-agent"}'
```
```json
{"status": "revoked", "agent": "compromised-agent", "revoked_count": 5}
```

### 7. Audit Dashboard

A Next.js dashboard showing a real-time log of every request. Each entry includes: timestamp, requester identity, secret name (not value), environment, task, policy matched, outcome, and duration of access.

Anomaly detection flags unusual patterns:
- **Frequency spike**: >10 requests in 5 minutes from the same requester
- **Off-hours access**: Production requests outside 06:00-22:00
- **New requester**: First-ever request from an unknown identity

### 8. SSH Key Brokering

A separate SSH key registry where developers register public keys with metadata. Before a key can be used, it must be approved by policy. The dashboard shows per-key usage and flags unencrypted private keys.

This extends 1Password's SSH agent feature with a policy and approval layer.

## 1Password Integration

- Uses the **1Password Python SDK** (`onepassword-sdk`) to fetch secrets from a real vault
- Secret references follow the `op://` URI format (`op://vault/item/field`) matching the `op run` mental model
- Audit log schema mirrors the **1Password Events API** (`/v1/signinattempts`, `/v1/itemusages`)
- SSH key brokering extends the **1Password SSH agent** with a policy and approval layer it doesn't currently have
- Runs fully in **demo mode** without a 1Password account (deterministic mock secrets)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the dashboard)

### Backend Setup

```bash
cd agentgate

# Install
pip install -e .

# (Optional) Copy and edit .env
cp .env.example .env

# Validate policies
agentgate policy validate
agentgate policy list

# Start the API server
agentgate server start
```

The server starts at `http://localhost:8000` in demo mode by default. Visit `/docs` for the interactive Swagger UI.

### Dashboard Setup

```bash
cd dashboard
npm install
npm run dev
```

The dashboard runs at `http://localhost:3000` and proxies API calls to the backend.

### Run the Demo

```bash
# In a separate terminal, with the server running:
python demo/agent_demo.py
```

This demonstrates the full two-phase flow: grant requests, secret exchange, denied requests, bulk revocation, rate limiting, and anomaly detection.

### CLI Demo

```bash
# Inject secrets into a subprocess
agentgate run --task deploy --env development -- env

# With explicit env var mapping
agentgate run --task deploy --secret "op://dev-vault/api-key/credential=MY_API_KEY" -- env

# View audit trail
agentgate audit tail
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Server info |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/policies` | List loaded policies |
| `POST` | `/agent/request-secret` | Phase 1: Request a credential grant (no secret) |
| `POST` | `/agent/exchange` | Phase 2: Exchange grant_id for the actual secret |
| `POST` | `/agent/release` | Release a grant early |
| `POST` | `/agent/revoke-agent` | Revoke ALL grants for an agent |
| `GET` | `/audit/logs` | Query audit logs (filterable) |
| `GET` | `/audit/stats` | Dashboard statistics |
| `WS` | `/audit/live` | Real-time audit WebSocket |
| `GET` | `/ssh/keys` | List registered SSH keys |
| `POST` | `/ssh/keys` | Register a new SSH key |
| `POST` | `/ssh/keys/request` | Request SSH key access |

## Configuration

AgentGate reads configuration from environment variables (with `AGENTGATE_` prefix) or a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTGATE_MODE` | `demo` | `demo` for mock secrets, `live` for real 1Password |
| `AGENTGATE_OP_SERVICE_ACCOUNT_TOKEN` | | 1Password token (required for `live` mode) |
| `AGENTGATE_AGENT_TOKEN` | `demo-token-12345` | Bearer token for agent API auth |
| `AGENTGATE_DB_URL` | `sqlite+aiosqlite:///./agentgate.db` | Database URL |
| `AGENTGATE_POLICY_DIR` | `./policies` | Path to YAML policy files |
| `AGENTGATE_RATE_LIMIT_PER_MINUTE` | `30` | Max requests per agent per minute |

## Design Decisions

- **Two-phase grant flow**: The secret is never returned during authorization. Phase 1 issues an opaque grant token; Phase 2 exchanges it for the secret. This means a leaked grant_id alone is useless after the grant expires or is consumed.
- **Deny-by-default policy model**: `policies/default.yaml` contains a catch-all deny rule at priority 0. All allow rules must have priority > 0.
- **Secrets never touch disk**: The secret value exists only in memory -- in the subprocess environment for CLI mode, or in the JSON response for API mode. The audit log stores only the `op://` reference, never the value.
- **Rate limiting is enforcement, not just monitoring**: Unlike the anomaly detection (which flags but doesn't block), rate limiting actively rejects excessive requests with HTTP 429.
- **Demo mode as first-class citizen**: The `MockSecretProvider` returns consistent, clearly-fake values (prefixed with `demo-`). The entire system runs end-to-end without any 1Password account.
- **Background TTL enforcement**: When a grant is issued, `asyncio.create_task` schedules automatic revocation. For CLI, TTL is implicit: subprocess exits and environment is cleared.
- **Anomaly detection is transparent**: Three rule-based heuristics produce a 0-1 score. No opaque ML models -- everything is explainable.
- **Helpful error messages**: Denied requests explain which policy blocked the request (or that no matching policy exists), what conditions were checked, and how to fix it.

## Stretch Goals

- **Slack approval workflow**: For secrets marked `require_approval: true`, send approve/deny buttons to a Slack channel before issuing the grant.
- **GitHub Actions integration**: A reusable action that configures AgentGate as the credential source, replacing `secrets: {}` injections.
- **MCP tool server**: Expose AgentGate as an MCP server so Claude or other agents can request credentials natively through tool use.
- **SIEM export**: Audit log export endpoint that posts to webhook endpoints in the same format as the 1Password Events API.

## License

MIT
