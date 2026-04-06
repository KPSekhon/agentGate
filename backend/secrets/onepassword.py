from __future__ import annotations


class OnePasswordProvider:
    """Fetch secrets from 1Password using the official SDK.

    Requires ``onepassword-sdk`` to be installed and a valid
    ``OP_SERVICE_ACCOUNT_TOKEN`` in the environment.
    """

    def __init__(self, service_account_token: str) -> None:
        self._token = service_account_token
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                from onepassword.client import Client
            except ImportError as exc:
                raise RuntimeError(
                    "Install onepassword-sdk: pip install 'agentgate[onepassword]'"
                ) from exc
            self._client = await Client.authenticate(
                auth=self._token,
                integration_name="AgentGate",
                integration_version="0.1.0",
            )
        return self._client

    async def resolve(self, secret_ref: str) -> str:
        """Resolve an ``op://vault/item/field`` reference."""
        client = await self._get_client()
        return await client.secrets.resolve(secret_ref)

    async def resolve_ssh_key(self, key_name: str) -> str:
        """Resolve an SSH key stored in 1Password."""
        client = await self._get_client()
        ref = f"op://SSH Keys/{key_name}/private key?ssh-format=openssh"
        return await client.secrets.resolve(ref)
