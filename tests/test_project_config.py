"""Tests for .agentgate.yaml project configuration."""
from __future__ import annotations

from pathlib import Path

from backend.project_config import load_project_config, ProjectConfig


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / ".agentgate.yaml"
    config_file.write_text("""
environment: staging
task: deploy
secrets:
  - ref: "op://vault/api-key/cred"
    env_var: "API_KEY"
  - ref: "op://vault/db/password"
    env_var: "DATABASE_PASSWORD"
""")

    config = load_project_config(tmp_path)
    assert config is not None
    assert config.environment == "staging"
    assert config.task == "deploy"
    assert len(config.secrets) == 2
    assert config.secrets[0].ref == "op://vault/api-key/cred"
    assert config.secrets[0].env_var == "API_KEY"
    assert config.secrets[1].env_var == "DATABASE_PASSWORD"


def test_load_config_not_found(tmp_path):
    config = load_project_config(tmp_path)
    assert config is None


def test_load_config_searches_parents(tmp_path):
    # Put config in parent
    config_file = tmp_path / ".agentgate.yaml"
    config_file.write_text("""
environment: production
task: build
secrets:
  - ref: "op://vault/token/value"
    env_var: "TOKEN"
""")

    # Search from a subdirectory
    sub = tmp_path / "src" / "app"
    sub.mkdir(parents=True)

    config = load_project_config(sub)
    assert config is not None
    assert config.environment == "production"
    assert len(config.secrets) == 1


def test_load_config_empty_file(tmp_path):
    config_file = tmp_path / ".agentgate.yaml"
    config_file.write_text("")

    config = load_project_config(tmp_path)
    assert config is not None
    assert config.secrets == []
