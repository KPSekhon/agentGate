from __future__ import annotations

from backend.config import settings
from backend.secrets.mock import MockSecretProvider
from backend.secrets.onepassword import OnePasswordProvider
from backend.secrets.op_cli import OpCliProvider


def create_secret_provider() -> MockSecretProvider | OnePasswordProvider | OpCliProvider:
    """Pick how secrets get resolved.

    demo -> deterministic fakes, no external dependency.
    cli  -> the 1Password CLI, reusing the developer's own desktop session.
    live -> the 1Password SDK with a service account, for servers and CI.
    """
    if settings.mode == "demo":
        return MockSecretProvider()

    if settings.mode == "cli":
        return OpCliProvider(op_path=settings.op_cli_path)

    if not settings.op_service_account_token:
        raise RuntimeError(
            "AGENTGATE_OP_SERVICE_ACCOUNT_TOKEN is required when mode=live"
        )
    return OnePasswordProvider(settings.op_service_account_token)
