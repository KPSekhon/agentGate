# agentgate

a runtime credential broker for ai agents. because giving your agent a raw `.env` file and hoping for the best is not a security strategy.

[![CI](https://github.com/KPSekhon/agentGate/actions/workflows/ci.yml/badge.svg)](https://github.com/KPSekhon/agentGate/actions/workflows/ci.yml)
&nbsp;Rust · Go · Python · TypeScript

---

<!-- replace with your youtube link -->
[![watch the demo](https://img.shields.io/badge/watch%20demo-youtube-red?style=for-the-badge&logo=youtube)](https://youtu.be/jI86jMFL8Z0)

---

## the problem

ai agents need secrets to do anything useful -- api keys, database passwords, deploy tokens. right now those secrets live in `.env` files, get pasted into ci configs, embedded in llm prompts, and shared over slack. there's no ttl, no scope, no audit trail, and no kill switch when an agent goes rogue.

agentgate sits between your agent and your secrets. agents request access for a specific task, get a time-scoped grant, and never see the actual secret until they explicitly exchange the grant for it. every request hits a yaml policy engine, every grant has a ttl and use limit, and every action is logged.

## architecture

agentgate is a multi-language system. each component is built in the language that fits its job.

```
 ai agent
    │
    │  HTTPS / mTLS
    ▼
┌────────────────────────┐
│  agentgate-proxy (Go)  │   network edge
│                        │
│  • rate limiting       │
│  • mTLS termination    │
│  • bearer auth         │
│  • token verification  │
│    (public key only)   │
│  • health / metrics    │
└───────────┬────────────┘
            │  HTTP (reverse proxy)
            ▼
┌────────────────────────┐
│  backend (Python)      │   enforcement point (PEP)
│  + dashboard (TS)      │
│                        │
│  • REST API            │
│  • grant persistence   │
│  • secret resolution   │
│    (1Password SDK)     │
│  • audit + dashboard   │
└───────────┬────────────┘
            │  gRPC: EvaluatePolicy
            │  (falls back to native engine if core is down)
            ▼
┌────────────────────────┐
│  agentgate-core (Rust) │   decision point (PDP)
│                        │
│  • Ed25519 token       │
│    engine              │
│  • policy engine       │
│    (glob matching)     │
│  • grant lifecycle     │
│  • anomaly scoring     │
│  • gRPC service        │
└────────────────────────┘
```

a request flows agent → Go proxy → Python backend → Rust core. the backend is the **policy enforcement point** (PEP): it owns the REST surface, grant persistence, and secret resolution. the core is the **policy decision point** (PDP): the backend delegates the allow/deny call to it over gRPC, and falls back to a native Python engine if the core is unreachable (so demo mode runs with the core off).

**why this split:**
- **Rust** is the decision point -- cryptographic token minting/verification and policy evaluation. the security-critical logic, with memory safety and no GC pauses.
- **Go** is the network edge -- concurrent connection handling, mTLS, rate limiting, and health checks. it also verifies grant tokens using only the published public key, so forged tokens are dropped before they reach the backend.
- **Python** is the enforcement point and orchestration layer -- REST API, grant persistence, 1Password SDK, secret resolution, CLI, and dashboard. fast to iterate on, rich ecosystem.

## how it works

the core idea is a **two-phase grant flow**. the agent never gets the secret on the first call.

```
 ai agent                    agentgate                     1password
 --------                    ---------                     ---------
    |                            |                              |
    |-- phase 1: request ------>|                              |
    |   (agent, env, task, ref) |-- evaluate policy            |
    |                           |-- check rate limit           |
    |                           |-- log "granted"              |
    |<-- grant_id + metadata ---|   (no secret here)           |
    |                           |                              |
    |-- phase 2: exchange ----->|                              |
    |   (grant_id)              |-- validate grant             |
    |                           |-- decrement uses ----------->|-- resolve secret
    |                           |<-----------------------------|
    |<-- secret_value ----------|                              |
    |                           |-- log "exchanged"            |
    |                           |                              |
    |-- release --------------->|                              |
    |   (grant_id)              |-- revoke grant               |
    |                           |-- log "released"             |
```

phase 1 gives you a grant token. phase 2 gives you the secret. the grant is single-use by default -- once you exchange it, it's gone. if you never exchange it, it auto-expires.

## what it does

### two-phase credential grant

phase 1 -- request a grant (you get a token, not the secret):
```bash
curl -X POST http://localhost:8000/agent/request-secret \
  -H "Authorization: Bearer demo-token-12345" \
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
  "expires_at": "2026-04-13T17:05:00Z",
  "ttl_seconds": 300,
  "uses_remaining": 1,
  "policy": "demo-agent-access"
}
```

phase 2 -- exchange that token for the actual secret:
```bash
curl -X POST http://localhost:8000/agent/exchange \
  -H "Authorization: Bearer demo-token-12345" \
  -d '{"grant_id": "a1b2c3d4-..."}'
```
```json
{
  "grant_id": "a1b2c3d4-...",
  "secret_value": "demo-openai-key-...",
  "uses_remaining": 0
}
```

uses_remaining hits 0 and the grant is auto-revoked. try to exchange it again and you get a 410 gone.

### yaml policies (deny by default)

everything is denied unless a policy explicitly allows it. policies are yaml files with glob matching and priority ordering.

```yaml
# policies/demo-agent.yaml
name: demo-agent-access
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

the engine checks requester identity, secret ref, environment, task, and ttl -- then picks the highest-priority matching policy. explicit deny rules short-circuit everything.

a catch-all deny at priority 0 means if you don't write a policy for it, it's blocked.

### rate limiting

10 requests per minute per agent (configurable). exceed it and you get a 429. the event is logged so you can see who's hammering your secrets.

### bulk revocation

agent compromised? one call kills every active grant it holds:

```bash
curl -X POST http://localhost:8000/agent/revoke-agent \
  -d '{"agent_name": "compromised-agent"}'
```
```json
{"status": "revoked", "agent": "compromised-agent", "revoked_count": 5}
```

### cli runtime injection

wrap any command and agentgate injects secrets into the subprocess environment. they never touch disk, never show up in shell history, and disappear when the process exits.

```bash
# auto-discover from policies
agentgate run --task deploy --env staging -- ./deploy.sh

# explicit mapping
agentgate run --task deploy \
  --secret "op://vault/api-key/cred=OPENAI_API_KEY" \
  --secret "op://vault/db/pass=DATABASE_PASSWORD" \
  -- ./deploy.sh

# or use a project config file
agentgate run -- ./deploy.sh
```

### project config (`.agentgate.yaml`)

drop this in your repo root and `agentgate run` picks it up automatically:

```yaml
environment: staging
task: deploy
secrets:
  - ref: "op://prod-vault/openai/api-key"
    env_var: "OPENAI_API_KEY"
  - ref: "op://prod-vault/database/password"
    env_var: "DATABASE_PASSWORD"
```

no more `--secret` flags. no more scripts expecting `OPENAI_API_KEY` but getting `op___prod_vault___openai___api_key` because the cli auto-generated the name from the path.

### audit dashboard

a next.js dashboard that shows everything happening in real time:

- **stat cards** -- total requests, grants, denials, active grants at a glance
- **audit table** -- filterable log of every action with requester, secret ref, policy matched, and outcome
- **live feed** -- websocket-powered, updates as events happen
- **policy viewer** -- see all loaded policies with yaml preview

anomaly detection runs three heuristics and scores each request 0-1:
- frequency spike: >10 requests in 5 min from the same agent (+0.4)
- off-hours production access: requests outside 06:00-22:00 utc (+0.3)
- new requester: never seen this identity before (+0.3)

no ml. no black boxes. just rules you can read and change.

### ssh key brokering

register ssh public keys with metadata. before a key can be used, policy has to approve it. the dashboard tracks per-key usage and flags unencrypted private keys.

## 1password integration

three ways to resolve secrets, picked by `AGENTGATE_MODE`:

| mode | resolver | when |
|------|----------|------|
| `demo` | deterministic fakes | no account needed, runs anywhere |
| `cli` | the 1password cli (`op read`) | local dev — reuses your desktop session and biometric unlock, no service account to mint |
| `live` | the 1password python sdk | servers and ci — service account tokens are auditable and non-interactive |

- uses the 1password python sdk to resolve secrets from real vaults
- secret refs use the `op://vault/item/field` uri format
- audit schema mirrors the 1password events api
- ssh brokering extends the 1password ssh agent with a policy layer
- runs fully in **demo mode** without any 1password account -- mock secrets are deterministic and clearly fake

## getting started

**prerequisites:** python 3.11+, node 18+, rust 1.75+, go 1.22+

```bash
# install python backend
pip install -e .

# build the rust core
cd agentgate-core && cargo build --release

# build the go proxy
cd agentgate-proxy && go build -o bin/agentgate-proxy ./cmd/proxy

# or build everything at once
make build
```

### running the full stack

```bash
# 1. start the rust core (gRPC on :50051)
make serve-core

# 2. start the go proxy (HTTPS on :8443, forwards to backend)
make serve-proxy

# 3. start the python backend (REST on :8000)
make serve-backend

# 4. start the dashboard (on :3000)
make serve-dashboard
```

### quick start (python-only, demo mode)

```bash
agentgate server   # REST API at http://localhost:8000/docs
cd dashboard && npm install && npm run dev  # dashboard at http://localhost:3000
python demo/quick_demo.py  # 60-second demo
```

### running tests

```bash
make test          # all tests (rust + go + python)
make rust-test     # 27 rust tests (incl. property-based + fuzz-style crypto tests)
make go-test       # 25 go tests (rate limiting, auth, edge token verification)
make python-test   # 30 python tests (policy, api, anomaly)

# the python -> rust gRPC seam (skips if the core isn't running):
#   agentgate serve --addr 127.0.0.1:50051 --policy-dir policies
python -m pytest tests/test_core_integration.py -v   # 8 integration tests (policy + token crypto + public key)
```

### rust cli

```bash
# validate policy files
agentgate policy-check --policy-dir policies/

# dry-run a policy evaluation
agentgate policy-eval \
  --policy-dir policies/ \
  --requester "agent:github-actions" \
  --environment ci \
  --task deploy \
  --secret-ref "op://ci-vault/deploy-key/credential"

# generate a PKCS#8 ed25519 signing key
agentgate keygen --out signing-key.p8

# start the gRPC server
agentgate serve --addr 0.0.0.0:50051 --policy-dir policies/ --signing-key signing-key.p8
```

## api

| method | path | what it does |
|--------|------|--------------|
| `GET` | `/` | server info |
| `GET` | `/docs` | swagger ui |
| `GET` | `/publickey` | ed25519 verification key (safe to publish; cannot mint) |
| `GET` | `/policies` | list loaded policies |
| `POST` | `/agent/request-secret` | phase 1: get a grant (no secret) |
| `POST` | `/agent/exchange` | phase 2: trade grant_id for the secret |
| `POST` | `/agent/release` | release a grant early |
| `POST` | `/agent/revoke-agent` | kill all grants for an agent |
| `GET` | `/audit/logs` | query audit logs |
| `GET` | `/audit/stats` | dashboard stats |
| `WS` | `/audit/live` | real-time audit websocket |
| `GET` | `/ssh/keys` | list ssh keys |
| `POST` | `/ssh/keys` | register a key |
| `POST` | `/ssh/keys/request` | request key access |

## config

all env vars use the `AGENTGATE_` prefix. or put them in a `.env` file.

| variable | default | what it does |
|----------|---------|--------------|
| `AGENTGATE_MODE` | `demo` | `demo` = mock secrets, `cli` = 1password cli (`op`), `live` = 1password sdk |
| `AGENTGATE_OP_CLI_PATH` | `op` | path to the 1password cli binary (mode=cli) |
| `AGENTGATE_OP_SERVICE_ACCOUNT_TOKEN` | | 1password token (required for live mode) |
| `AGENTGATE_AGENT_TOKEN` | `demo-token-12345` | bearer token for api auth |
| `AGENTGATE_DB_URL` | `sqlite+aiosqlite:///./agentgate.db` | database url |
| `AGENTGATE_POLICY_DIR` | `./policies` | where your yaml policies live |
| `AGENTGATE_RATE_LIMIT_PER_MINUTE` | `10` | max requests per agent per minute |
| `AGENTGATE_CORE_URL` | | delegate policy decisions to the rust core over gRPC (e.g. `localhost:50051`); unset = native python engine |

**rust core (`agentgate-core`)**

| variable | default | what it does |
|----------|---------|--------------|
| `AGENTGATE_SIGNING_KEY` | (ephemeral) | path to a PKCS#8 Ed25519 signing key (`agentgate keygen`); keeps tokens valid across restarts |

**go proxy (`agentgate-proxy`)**

| variable | default | what it does |
|----------|---------|--------------|
| `AGENTGATE_PROXY_ADDR` | `:8443` | proxy listen address |
| `AGENTGATE_BACKEND_URL` | `http://localhost:8000` | upstream backend url |
| `AGENTGATE_RATE_LIMIT` | `60` | proxy-level rate limit per agent/min |
| `AGENTGATE_RATE_BURST` | `10` | token bucket burst size |
| `AGENTGATE_TLS_CERT` | | tls certificate file (enables https) |
| `AGENTGATE_TLS_KEY` | | tls private key file |
| `AGENTGATE_TLS_CLIENT_CA` | | client ca for mtls (requires cert+key) |
| `AGENTGATE_PUBLIC_KEY` | (fetched) | hex ed25519 public key to pin; otherwise fetched from the backend |

## why it's built this way

- **two-phase flow** -- a leaked grant_id is useless after expiry or consumption. the secret only moves when the agent explicitly asks for it.
- **deny by default** -- `default.yaml` catches everything at priority 0. you have to opt in to access, not opt out.
- **secrets never touch disk** -- they exist in memory only. the audit log stores the `op://` reference, never the value.
- **cryptographic capability tokens** -- with the core wired in, a grant is an `ag2.<payload>.<sig>` token: **Ed25519**-signed claims (requester, secret_ref, expiry, uses, key id) minted by the Rust core. the agent presents it on exchange, and tampered, forged, or expired tokens are rejected at the Rust layer before the backend touches the database. because it's a public-key signature, verifiers need only the **public key** (published over a `PublicKey` RPC) — never the signing key. the token is stateless proof; use-count and revocation are enforced from persistent state. property-based tests assert any single-bit mutation is rejected. full write-up in [SECURITY.md](SECURITY.md), and the reasoning behind each choice is recorded in [docs/adr](docs/adr).
- **decision/enforcement split** -- the Python backend (PEP) delegates every allow/deny call and all token crypto to the Rust core (PDP) over gRPC, then resolves the secret itself. if the core is unreachable it falls back to an equivalent native engine, so a core outage degrades gracefully instead of taking the broker down.
- **rate limiting at two levels** -- the Go proxy enforces token-bucket rate limiting at the network edge. the Rust core enforces per-agent limits at the grant layer. both log violations.
- **mtls for agent identity** -- the Go proxy supports mutual TLS. agents present client certificates, and the proxy extracts the CN and forwards it as `X-Client-CN`. no more shared bearer tokens.
- **demo mode is a first-class citizen** -- the whole system runs end-to-end without any external accounts.
- **background ttl enforcement** -- the Rust core runs a periodic sweep to revoke expired grants. no polling required.
- **transparent anomaly detection** -- three rules, a score, no mystery. you can read every heuristic in `anomaly.py` and `grants.rs`.

## stack

| layer | language | key libraries |
|-------|----------|---------------|
| **core** (crypto, policy, grants) | Rust | `ring` (Ed25519), `tonic` (gRPC), `clap` (CLI), `serde`/`serde_yaml`, `proptest` (property tests) |
| **proxy** (network edge) | Go | stdlib `net/http`, `crypto/tls` (mTLS), `log/slog` (structured logging) |
| **backend** (orchestration) | Python | FastAPI, SQLAlchemy async, 1Password SDK, Click, Pydantic |
| **dashboard** (UI) | TypeScript | Next.js 14, React 18, Tailwind CSS, WebSocket live feed |

## license

mit
