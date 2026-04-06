from __future__ import annotations

from backend.config import settings
from backend.secrets.mock import MockSecretProvider
from backend.secrets.onepassword import OnePasswordProvider


def create_secret_provider() -> MockSecretProvider | OnePasswordProvider:
    if settings.mode == "demo":
        return MockSecretProvider()

    if not settings.op_service_account_token:
        raise RuntimeError(
            "AGENTGATE_OP_SERVICE_ACCOUNT_TOKEN is required when mode=live"
        )
    return OnePasswordProvider(settings.op_service_account_token)
