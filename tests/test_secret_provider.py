from __future__ import annotations

import pytest
from backend.secrets.mock import MockSecretProvider


@pytest.mark.asyncio
async def test_mock_resolve_deterministic():
    provider = MockSecretProvider()
    val1 = await provider.resolve("op://demo-vault/api-key/credential")
    val2 = await provider.resolve("op://demo-vault/api-key/credential")
    assert val1 == val2
    assert val1.startswith("demo-api-key-")


@pytest.mark.asyncio
async def test_mock_resolve_different_refs():
    provider = MockSecretProvider()
    val1 = await provider.resolve("op://vault/item-a/field")
    val2 = await provider.resolve("op://vault/item-b/field")
    assert val1 != val2


@pytest.mark.asyncio
async def test_mock_ssh_key():
    provider = MockSecretProvider()
    key = await provider.resolve_ssh_key("test-key")
    assert "OPENSSH PRIVATE KEY" in key
