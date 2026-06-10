from __future__ import annotations

import logging

import grpc

from backend.grpc_gen import agentgate_pb2, agentgate_pb2_grpc
from backend.policy.types import Grant, Policy

logger = logging.getLogger("agentgate.core_client")


class CoreClient:
    """gRPC client for the Rust core (the Policy Decision Point).

    The backend delegates the allow/deny decision to the Rust core, which owns
    the cryptographic token engine and policy evaluation. If the core is
    unreachable, callers fall back to the native Python policy engine, so the
    system degrades gracefully and demo mode keeps working without the core.
    """

    def __init__(self, address: str, timeout: float = 2.0) -> None:
        self.address = address
        self.timeout = timeout
        self._channel = grpc.insecure_channel(address)
        self._stub = agentgate_pb2_grpc.AgentGateStub(self._channel)

    def evaluate(
        self,
        requester: str,
        environment: str,
        task: str,
        secret_ref: str,
    ) -> tuple[Grant | None, Policy | None]:
        """Ask the Rust core for a policy decision.

        Returns (grant, policy) mirroring the native PolicyEngine.evaluate
        signature. Raises grpc.RpcError if the core is unreachable — the caller
        decides whether to fall back.
        """
        request = agentgate_pb2.PolicyEvalRequest(
            requester=requester,
            environment=environment,
            task=task,
            secret_ref=secret_ref,
        )
        response = self._stub.EvaluatePolicy(request, timeout=self.timeout)

        policy = Policy(name=response.policy_name) if response.policy_name else None

        if not response.allowed:
            return None, policy

        grant = Grant(
            secret_ref=secret_ref,
            ttl_seconds=response.ttl_seconds,
            max_uses=response.max_uses,
        )
        return grant, policy

    def mint_token(
        self,
        *,
        grant_id: str,
        requester: str,
        secret_ref: str,
        environment: str,
        task: str,
        issued_at: int,
        expires_at: int,
        max_uses: int,
        policy_name: str,
    ) -> str:
        """Ask the core to mint a signed (HMAC-SHA256) capability token.

        The returned ``ag1.<payload>.<sig>`` token embeds the grant's claims and
        becomes the credential the agent presents on exchange. Raises on failure
        so the caller can fall back to an unsigned id.
        """
        claims = agentgate_pb2.GrantClaims(
            grant_id=grant_id,
            requester=requester,
            secret_ref=secret_ref,
            environment=environment,
            task=task,
            issued_at=issued_at,
            expires_at=expires_at,
            max_uses=max_uses,
            policy_name=policy_name,
        )
        response = self._stub.MintToken(
            agentgate_pb2.MintTokenRequest(claims=claims), timeout=self.timeout
        )
        if response.error:
            raise RuntimeError(f"token mint failed: {response.error}")
        return response.token

    def verify_token(self, token: str) -> tuple[dict | None, str]:
        """Verify a capability token's signature and expiry via the core.

        Returns ``(claims, "")`` if valid, or ``(None, reason)`` if the token is
        tampered, forged, or expired. Use-count and revocation are enforced
        separately by the persistent grant store.
        """
        response = self._stub.VerifyToken(
            agentgate_pb2.VerifyTokenRequest(token=token), timeout=self.timeout
        )
        if not response.valid:
            return None, response.reason or "token verification failed"

        c = response.claims
        return {
            "grant_id": c.grant_id,
            "requester": c.requester,
            "secret_ref": c.secret_ref,
            "environment": c.environment,
            "task": c.task,
            "issued_at": c.issued_at,
            "expires_at": c.expires_at,
            "max_uses": c.max_uses,
            "policy_name": c.policy_name,
            "key_id": c.key_id,
        }, ""

    def public_key(self) -> dict:
        """Fetch the core's signing public key and id.

        Returns ``{"algorithm", "key_id", "public_key"}``. Verifiers can use the
        public key to validate tokens without ever holding the signing key.
        """
        response = self._stub.PublicKey(
            agentgate_pb2.PublicKeyRequest(), timeout=self.timeout
        )
        return {
            "algorithm": response.algorithm,
            "key_id": response.key_id,
            "public_key": response.public_key,
        }

    def health(self) -> bool:
        try:
            self._stub.HealthCheck(
                agentgate_pb2.HealthRequest(), timeout=self.timeout
            )
            return True
        except grpc.RpcError:
            return False

    def close(self) -> None:
        self._channel.close()
