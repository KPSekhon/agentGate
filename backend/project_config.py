"""Project-level configuration via .agentgate.yaml.

Lets projects declare what secrets they need and how to map them to env vars,
so `agentgate run` works without manual --secret flags.

Example .agentgate.yaml:

    environment: development
    task: deploy
    secrets:
      - ref: "op://prod-vault/openai/api-key"
        env_var: "OPENAI_API_KEY"
      - ref: "op://prod-vault/database/password"
        env_var: "DATABASE_URL"
      - ref: "op://prod-vault/github/token"
        env_var: "GH_TOKEN"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SecretMapping:
    ref: str
    env_var: str


@dataclass
class ProjectConfig:
    environment: str = "development"
    task: str = "default"
    secrets: list[SecretMapping] = field(default_factory=list)


def load_project_config(search_dir: Path | None = None) -> ProjectConfig | None:
    """Search for .agentgate.yaml in the given directory and parents. Returns None if not found."""
    start = search_dir or Path.cwd()
    current = start.resolve()

    for _ in range(20):  # max depth to prevent infinite loops
        candidate = current / ".agentgate.yaml"
        if candidate.exists():
            return _parse_config(candidate)
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _parse_config(path: Path) -> ProjectConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        return ProjectConfig()

    secrets = []
    for s in raw.get("secrets", []):
        secrets.append(SecretMapping(
            ref=s["ref"],
            env_var=s["env_var"],
        ))

    return ProjectConfig(
        environment=raw.get("environment", "development"),
        task=raw.get("task", "default"),
        secrets=secrets,
    )
