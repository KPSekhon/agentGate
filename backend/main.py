from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agent.routes import router as agent_router, set_session_manager
from backend.agent.session import AgentSessionManager
from backend.audit.routes import router as audit_router
from backend.config import settings
from backend.database import init_db
from backend.policy.engine import PolicyEngine
from backend.schemas import PolicyOut
from backend.secrets.factory import create_secret_provider
from backend.ssh.registry import SSHKeyRegistry
from backend.ssh.routes import router as ssh_router, set_ssh_registry

_policy_engine: PolicyEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _policy_engine

    await init_db()

    core_client = None
    if settings.core_url:
        from backend.core_client import CoreClient

        core_client = CoreClient(settings.core_url)
        if core_client.health():
            print(f"[agentgate] policy decisions delegated to Rust core at {settings.core_url}")
        else:
            print(f"[agentgate] Rust core at {settings.core_url} unreachable — using native engine with fallback")

    _policy_engine = PolicyEngine(settings.policy_dir, core_client=core_client)
    provider = create_secret_provider()

    manager = AgentSessionManager(_policy_engine, provider)
    set_session_manager(manager)

    registry = SSHKeyRegistry(_policy_engine, provider)
    set_ssh_registry(registry)

    yield


app = FastAPI(
    title="AgentGate",
    description="Runtime Credential Broker for AI Agents and Developer Workflows",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(audit_router)
app.include_router(ssh_router)


@app.get("/")
async def root():
    return {
        "name": "AgentGate",
        "version": "0.1.0",
        "mode": settings.mode,
        "docs": "/docs",
    }


@app.get("/policies", response_model=list[PolicyOut])
async def list_policies():
    if _policy_engine is None:
        return []
    results = []
    for p in _policy_engine.policies:
        results.append(PolicyOut(
            name=p.name,
            description=p.description,
            priority=p.priority,
            deny=p.deny,
            conditions=[
                {"requester": c.requester, "environment": c.environment, "task": c.task}
                for c in p.conditions
            ],
            grants=[
                {"secret_ref": g.secret_ref, "ttl_seconds": g.ttl_seconds, "max_uses": g.max_uses}
                for g in p.grants
            ],
        ))
    return results
