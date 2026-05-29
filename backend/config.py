from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mode: Literal["live", "demo"] = "demo"
    op_service_account_token: str = ""
    agent_token: str = "demo-token-12345"
    db_url: str = "sqlite+aiosqlite:///./agentgate.db"
    policy_dir: str = "./policies"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    rate_limit_per_minute: int = 10

    # When set (e.g. "localhost:50051"), the backend delegates policy decisions
    # to the Rust core over gRPC. The backend remains the enforcement point.
    # Unset = use the native Python policy engine (demo mode default).
    core_url: str = ""

    model_config = {
        "env_prefix": "AGENTGATE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
