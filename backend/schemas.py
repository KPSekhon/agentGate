from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# --- Audit ---

class AuditLogOut(BaseModel):
    id: str
    timestamp: datetime
    requester: str
    environment: str
    task: str
    secret_ref: str
    action: str
    policy_name: str
    ttl_seconds: int
    anomaly_score: float

    model_config = {"from_attributes": True}


class AuditStats(BaseModel):
    total_requests_today: int
    denied_requests_today: int
    active_grants: int
    anomaly_alerts_today: int


# --- Agent ---

class SecretRequest(BaseModel):
    agent_name: str
    environment: str
    task: str
    secret_ref: str
    requested_ttl: int = 300


class SecretResponse(BaseModel):
    grant_id: str
    secret_value: str
    expires_at: datetime
    ttl_seconds: int
    policy: str


class DeniedResponse(BaseModel):
    error: str
    reason: str


class ReleaseRequest(BaseModel):
    grant_id: str


# --- SSH ---

class SSHKeyOut(BaseModel):
    id: str
    name: str
    fingerprint: str
    key_type: str
    has_passphrase: bool
    description: str
    created_at: datetime
    last_used_at: datetime | None
    last_used_by: str
    access_count: int

    model_config = {"from_attributes": True}


class SSHKeyRequest(BaseModel):
    requester: str
    environment: str
    task: str
    key_name: str


class SSHKeyRegister(BaseModel):
    name: str
    fingerprint: str
    key_type: str = "rsa"
    has_passphrase: bool = True
    description: str = ""


# --- Policies ---

class PolicyOut(BaseModel):
    name: str
    description: str
    priority: int
    deny: bool
    conditions: list[dict]
    grants: list[dict]
