from __future__ import annotations

from typing import Protocol


class SecretProvider(Protocol):
    """Abstract interface for resolving secret references to values."""

    async def resolve(self, secret_ref: str) -> str:
        """Resolve an op:// secret reference to its plaintext value."""
        ...

    async def resolve_ssh_key(self, key_name: str) -> str:
        """Resolve an SSH key by name, returning the private key material."""
        ...
