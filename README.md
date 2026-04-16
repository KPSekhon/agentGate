# agentgate

a runtime credential broker for ai agents. because giving your agent a raw `.env` file and hoping for the best is not a security strategy.

---

<!-- replace with your youtube link -->
[![watch the demo](https://img.shields.io/badge/watch%20demo-youtube-red?style=for-the-badge&logo=youtube)](https://youtu.be/jI86jMFL8Z0)

---

## the problem

ai agents need secrets to do anything useful -- api keys, database passwords, deploy tokens. right now those secrets live in `.env` files, get pasted into ci configs, embedded in llm prompts, and shared over slack. there's no ttl, no scope, no audit trail, and no kill switch when an agent goes rogue.

agentgate sits between your agent and your secrets. agents request access for a specific task, get a time-scoped grant, and never see the actual secret until they explicitly exchange the grant for it. every request hits a yaml policy engine, every grant has a ttl and use limit, and every action is logged.

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

- uses the 1password python sdk to resolve secrets from real vaults
- secret refs use the `op://vault/item/field` uri format
- audit schema mirrors the 1password events api
- ssh brokering extends the 1password ssh agent with a policy layer
- runs fully in **demo mode** without any 1password account -- mock secrets are deterministic and clearly fake

## getting started

you need python 3.11+ and node 18+ (for the dashboard).

```bash
# install
pip install -e .

# check your policies
agentgate policy validate
agentgate policy list

# start the server (demo mode, no 1password needed)
agentgate server
```

server runs at `http://localhost:8000`. hit `/docs` for the swagger ui.

```bash
# start the dashboard
cd dashboard && npm install && npm run dev
```

dashboard runs at `http://localhost:3000`, proxies api calls to the backend.

```bash
# run the 60-second demo (good for screen recording)
python demo/quick_demo.py

# or the full feature demo
python demo/agent_demo.py
```

## api

| method | path | what it does |
|--------|------|--------------|
| `GET` | `/` | server info |
| `GET` | `/docs` | swagger ui |
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
| `AGENTGATE_MODE` | `demo` | `demo` = mock secrets, `live` = real 1password |
| `AGENTGATE_OP_SERVICE_ACCOUNT_TOKEN` | | 1password token (required for live mode) |
| `AGENTGATE_AGENT_TOKEN` | `demo-token-12345` | bearer token for api auth |
| `AGENTGATE_DB_URL` | `sqlite+aiosqlite:///./agentgate.db` | database url |
| `AGENTGATE_POLICY_DIR` | `./policies` | where your yaml policies live |
| `AGENTGATE_RATE_LIMIT_PER_MINUTE` | `10` | max requests per agent per minute |

## why it's built this way

- **two-phase flow** -- a leaked grant_id is useless after expiry or consumption. the secret only moves when the agent explicitly asks for it.
- **deny by default** -- `default.yaml` catches everything at priority 0. you have to opt in to access, not opt out.
- **secrets never touch disk** -- they exist in memory only. the audit log stores the `op://` reference, never the value.
- **rate limiting is enforcement** -- anomaly detection flags things. rate limiting actually blocks them. 429, not a warning.
- **demo mode is a first-class citizen** -- the whole system runs end-to-end without any external accounts.
- **background ttl enforcement** -- asyncio tasks auto-revoke expired grants. you don't have to poll.
- **transparent anomaly detection** -- three rules, a score, no mystery. you can read every heuristic in `anomaly.py`.

## stack

python 3.11+ / fastapi / sqlalchemy async / aiosqlite / pydantic / click
next.js 14 / typescript / tailwind css
websocket live feed / bearer token auth / sqlite

## license

mit
