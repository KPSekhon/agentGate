from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Policy:
    name: str
    description: str = ""
    priority: int = 0
    conditions: list[Condition] = field(default_factory=list)
    grants: list[Grant] = field(default_factory=list)
    deny: bool = False


@dataclass
class Condition:
    requester: str = "*"
    environment: str = "*"
    task: str = "*"


@dataclass
class Grant:
    secret_ref: str
    ttl_seconds: int = 300
    max_uses: int = 1
