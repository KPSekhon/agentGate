# AgentGate

**Runtime Credential Broker for AI Agents and Developer Workflows**

AgentGate gives AI agents, scripts, and CI pipelines scoped, time-limited access to secrets — with policy enforcement, zero plaintext exposure, and full audit trails. Built on the 1Password SDK.

---

## The Problem

Modern developer workflows have a secret sprawl problem. Credentials live in `.env` files checked into repos, pasted into CI configs, embedded in LLM prompts, and shared over Slack. AI agents make this worse: they need credentials to be useful, but giving an agent unrestricted access to secrets is a governance disaster waiting to happen.

AgentGate solves this by acting as a **credential broker** — agents and scripts request access for a specific task, get a time-scoped grant, and never see the raw secret in plaintext storage. Every request is evaluated against a YAML policy, every grant has a TTL, and every action is logged.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  AI Agent    │────>│              │────>│                 │
│  (REST API)  │     │              │     │  1Password SDK  │
├─────────────┤     │  AgentGate   │     │  (or Mock)      │
│  CLI User   │────>│  Policy      │     │                 │
│  (agentgate │     │  Engine      │     │  op://vault/    │
│   run ...)  │     │              │     │   item/field    │
├─────────────┤     │              │     └─────────────────┘
│  CI Pipeline│────>│              │
│  (GitHub    │     └──────┬───────┘
│   Actions)  │            │
└─────────────┘     ┌──────┴───────┐
                    │  Audit Log   │───> Dashboard (Next.js)
                    │  (SQLite)    │───> WebSocket Live Feed
                    └──────────────┘
```

## Features

### 1. Policy-Based Secret Access

YAML policies define who can request what, under which conditions. Deny by default — if no policy matches, the request is refused and logged.

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

### 2. Runtime Injection (CLI)

A thin CLI wrapper that fetches secrets at runtime, injects them into a subprocess, and clears them after exit. The secret never touches disk, never appears in shell history, and never exists outside the subprocess lifetime.

```bash
agentgate run --task deploy --env staging -- ./deploy.sh
```

This mirrors exactly what `op run` and `op inject` do in 1Password's CLI, with a policy enforcement layer on top.

### 3. Audit Dashboard

A Next.js dashboard showing a real-time log of every request. Each entry includes: timestamp, requester identity, secret name (not value), environment, task, policy matched, outcome, and duration of access.

Anomaly detection flags unusual patterns:
- **Frequency spike**: >10 requests in 5 minutes from the same requester
- **Off-hours access**: Production requests outside 06:00–22:00
- **New requester**: First-ever request from an unknown identity

### 4. SSH Key Brokering

A separate SSH key registry where developers register public keys with metadata. Before a key can be used, it must be approved by policy. The dashboard shows per-key usage and flags unencrypted private keys.

This extends 1Password's SSH agent feature with a policy and approval layer.

### 5. AI Agent Mode

A REST API that AI agents call with structured payloads to request time-limited credential grants:

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

Response (on success):
```json
{
  "grant_id": "a1b2c3d4-...",
  "secret_value": "demo-openai-key-...",
  "expires_at": "2026-04-05T17:05:00Z",
  "ttl_seconds": 300,
  "policy": "demo-agent-access"
}
```

Grants auto-expire via background tasks. Agents can also release grants early via `POST /agent/release`.

## 1Password Integration

- Uses the **1Password Python SDK** (`onepassword-sdk`) to fetch secrets from a real vault
- Secret references follow the `op://` URI format (`op://vault/item/field`) matching the `op run` mental model
- Audit log schema mirrors the **1Password Events API** (`/v1/signinattempts`, `/v1/itemusages`) — the audit export endpoint produces SIEM-compatible payloads
- SSH key brokering extends the **1Password SSH agent** with a policy and approval layer it doesn't currently have
- Runs fully in **demo mode** without a 1Password account (deterministic mock secrets)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the dashboard)

### Backend Setup

```bash
# Clone and install
cd agentgate
pip install -e .

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

This demonstrates the full flow: granted requests, denied requests, anomaly detection, and audit trail generation.

### CLI Demo

```bash
# Inject secrets into a subprocess
agentgate run --task deploy --env development -- env | grep DEMO

# View audit trail
agentgate audit tail
```

## Project Structure

```
agentgate/
├── backend/
│   ├── main.py              # FastAPI app with lifespan management
│   ├── config.py             # Pydantic settings (env-based)
│   ├── database.py           # Async SQLite via SQLAlchemy
│   ├── models.py             # AuditLog, SecretGrant, SSHKey
│   ├── schemas.py            # Pydantic request/response models
│   ├── policy/
│   │   ├── engine.py         # Policy evaluation (deny-by-default)
│   │   ├── loader.py         # YAML parsing and validation
│   │   └── types.py          # Policy, Condition, Grant dataclasses
│   ├── secrets/
│   │   ├── provider.py       # Abstract SecretProvider protocol
│   │   ├── onepassword.py    # 1Password SDK implementation
│   │   ├── mock.py           # Demo mode (deterministic fakes)
│   │   └── factory.py        # Provider selection based on config
│   ├── audit/
│   │   ├── logger.py         # Write + broadcast audit events
│   │   ├── anomaly.py        # Anomaly scoring heuristics
│   │   └── routes.py         # GET /audit/logs, /stats, WS /live
│   ├── agent/
│   │   ├── auth.py           # Bearer token validation
│   │   ├── session.py        # Grant lifecycle + TTL enforcement
│   │   └── routes.py         # POST /agent/request-secret, /release
│   ├── ssh/
│   │   ├── registry.py       # Key registration + policy checks
│   │   └── routes.py         # GET /ssh/keys, POST /ssh/keys/request
│   └── cli/
│       ├── main.py           # Click CLI group
│       ├── run.py            # agentgate run (subprocess injection)
│       ├── policy_cmd.py     # agentgate policy validate/list
│       ├── audit_cmd.py      # agentgate audit tail
│       └── server_cmd.py     # agentgate server start
├── dashboard/                # Next.js 14 + TypeScript + Tailwind
│   └── src/
│       ├── app/              # App Router pages (/, /audit, /agents, /policies, /ssh)
│       ├── components/       # Sidebar, AuditTable, LiveFeed, StatCard, etc.
│       └── lib/              # API client, WebSocket hook, TypeScript types
├── policies/                 # YAML policy files
│   ├── default.yaml          # Catch-all deny (priority 0)
│   ├── demo-agent.yaml       # Demo agent grants
│   ├── dev-team.yaml         # Developer access
│   └── ci-pipeline.yaml      # CI grants + production deny
├── demo/
│   ├── agent_demo.py         # Full agent flow demonstration
│   └── cli_demo.sh           # CLI workflow demonstration
└── tests/
    ├── test_policy_engine.py
    └── test_secret_provider.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Server info |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/policies` | List loaded policies |
| `POST` | `/agent/request-secret` | Request a credential grant |
| `POST` | `/agent/release` | Release a grant early |
| `GET` | `/audit/logs` | Query audit logs (filterable) |
| `GET` | `/audit/stats` | Dashboard statistics |
| `WS` | `/audit/live` | Real-time audit WebSocket |
| `GET` | `/ssh/keys` | List registered SSH keys |
| `POST` | `/ssh/keys` | Register a new SSH key |
| `POST` | `/ssh/keys/request` | Request SSH key access |

## Design Decisions

- **Deny-by-default policy model**: `policies/default.yaml` contains a catch-all deny rule at priority 0. All allow rules must have priority > 0.
- **Secrets never touch disk**: The secret value exists only in memory — in the subprocess environment for CLI mode, or in the JSON response for API mode. The audit log stores only the `op://` reference, never the value.
- **Demo mode as first-class citizen**: The `MockSecretProvider` returns consistent, clearly-fake values (prefixed with `demo-`). The entire system runs end-to-end without any 1Password account.
- **Background TTL enforcement**: When a grant is issued, `asyncio.create_task` schedules automatic revocation. For CLI, TTL is implicit: subprocess exits and environment is cleared.
- **Anomaly detection is transparent**: Three rule-based heuristics produce a 0–1 score. No opaque ML models — everything is explainable.

## Stretch Goals

- **Slack approval workflow**: For secrets marked `require_approval: true`, send approve/deny buttons to a Slack channel before issuing the grant.
- **GitHub Actions integration**: A reusable action that configures AgentGate as the credential source, replacing `secrets: {}` injections.
- **MCP tool server**: Expose AgentGate as an MCP server so Claude or other agents can request credentials natively through tool use.
- **SIEM export**: Audit log export endpoint that posts to webhook endpoints in the same format as the 1Password Events API.

## License

MIT
