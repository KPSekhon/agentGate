from __future__ import annotations

import hashlib

# Demo SSH key (RSA 2048 — NOT a real key, generated for testing only)
_DEMO_SSH_PRIVATE_KEY = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAlwAAAAdzc2gtcn
NhAAAAAwEAAQAAAIEA0Z1gq2Xr9sGfODGSR7bGR+H+demo+key+for+agentgate+test
+only+not+real+AAAQDRnWCrZev2wZ84MZJHtsZH4f6ehZ0k+demo+key+for+agentga
te+test+only+not+real+AAAAB3NzaC1yc2EAAAGBAMk=
-----END OPENSSH PRIVATE KEY-----"""


class MockSecretProvider:
    """Returns deterministic fake secrets for demo/testing. No external deps."""

    async def resolve(self, secret_ref: str) -> str:
        digest = hashlib.sha256(secret_ref.encode()).hexdigest()[:12]
        parts = secret_ref.replace("op://", "").split("/")
        prefix = parts[1] if len(parts) >= 2 else "secret"
        return f"demo-{prefix}-{digest}"

    async def resolve_ssh_key(self, key_name: str) -> str:
        return _DEMO_SSH_PRIVATE_KEY
