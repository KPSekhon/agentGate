from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    requester: Mapped[str] = mapped_column(String(255))
    environment: Mapped[str] = mapped_column(String(64))
    task: Mapped[str] = mapped_column(String(255))
    secret_ref: Mapped[str] = mapped_column(String(512))
    action: Mapped[str] = mapped_column(String(32))  # granted | denied | released | expired
    source_ip: Mapped[str] = mapped_column(String(64), default="")
    policy_name: Mapped[str] = mapped_column(String(255), default="")
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)


class SecretGrant(Base):
    __tablename__ = "secret_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    audit_log_id: Mapped[str] = mapped_column(String(36), ForeignKey("audit_logs.id"))
    requester: Mapped[str] = mapped_column(String(255))
    secret_ref: Mapped[str] = mapped_column(String(512))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uses_remaining: Mapped[int] = mapped_column(Integer, default=1)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class SSHKey(Base):
    __tablename__ = "ssh_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(512), default="")
    key_type: Mapped[str] = mapped_column(String(32), default="rsa")
    has_passphrase: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_by: Mapped[str] = mapped_column(String(255), default="")
    access_count: Mapped[int] = mapped_column(Integer, default=0)
