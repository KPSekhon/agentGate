from __future__ import annotations

from pathlib import Path

import yaml

from .types import Condition, Grant, Policy


def load_policies_from_directory(directory: str | Path) -> list[Policy]:
    """Load and parse all YAML policy files from a directory."""
    path = Path(directory)
    if not path.exists():
        return []

    policies: list[Policy] = []
    for file in sorted(path.glob("*.yaml")):
        try:
            policies.extend(load_policy_file(file))
        except Exception as exc:
            raise ValueError(f"Failed to parse {file.name}: {exc}") from exc

    return sorted(policies, key=lambda p: p.priority, reverse=True)


def load_policy_file(file: Path) -> list[Policy]:
    """Parse a single YAML policy file. Supports multi-document YAML (--- separator)."""
    text = file.read_text(encoding="utf-8")
    docs = list(yaml.safe_load_all(text))
    policies: list[Policy] = []
    for doc in docs:
        if doc is None:
            continue
        if isinstance(doc, list):
            policies.extend(_parse_policy(d) for d in doc)
        else:
            policies.append(_parse_policy(doc))
    return policies


def _parse_policy(data: dict) -> Policy:
    conditions = [
        Condition(
            requester=c.get("requester", "*"),
            environment=c.get("environment", "*"),
            task=c.get("task", "*"),
        )
        for c in data.get("conditions", [])
    ]

    grants = [
        Grant(
            secret_ref=g["secret_ref"],
            ttl_seconds=g.get("ttl_seconds", 300),
            max_uses=g.get("max_uses", 1),
        )
        for g in data.get("grants", [])
    ]

    return Policy(
        name=data["name"],
        description=data.get("description", ""),
        priority=data.get("priority", 0),
        conditions=conditions,
        grants=grants,
        deny=data.get("deny", False),
    )
