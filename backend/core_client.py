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
