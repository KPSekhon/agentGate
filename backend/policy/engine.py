from __future__ import annotations

import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING

from .loader import load_policies_from_directory
from .types import Grant, Policy

if TYPE_CHECKING:
    from backend.core_client import CoreClient

logger = logging.getLogger("agentgate.policy")


class PolicyEngine:
    """Evaluate access requests against loaded policies. Deny by default.

    When a CoreClient is attached, the allow/deny decision is delegated to the
    Rust core (the Policy Decision Point). If the core is unreachable, the
    engine falls back to native Python evaluation so the system degrades
    gracefully and demo mode works without the core running.
    """

    def __init__(
        self,
        policy_dir: str | Path | None = None,
        core_client: "CoreClient | None" = None,
    ) -> None:
        self.policies: list[Policy] = []
        self.core_client = core_client
        if policy_dir:
            self.load(policy_dir)

    def load(self, directory: str | Path) -> None:
        self.policies = load_policies_from_directory(directory)

    def evaluate(
        self,
        requester: str,
        environment: str,
        task: str,
        secret_ref: str,
    ) -> tuple[Grant | None, Policy | None]:
        """Return (grant, matched_policy) or (None, None) if denied."""
        if self.core_client is not None:
            try:
                return self.core_client.evaluate(
                    requester, environment, task, secret_ref
                )
            except Exception as exc:  # grpc.RpcError or channel failure
                logger.warning(
                    "core policy decision failed (%s); falling back to native engine",
                    exc,
                )

        return self._evaluate_native(requester, environment, task, secret_ref)

    def _evaluate_native(
        self,
        requester: str,
        environment: str,
        task: str,
        secret_ref: str,
    ) -> tuple[Grant | None, Policy | None]:
        for policy in self.policies:
            if not self._conditions_match(policy, requester, environment, task):
                continue

            if policy.deny:
                return None, policy

            for grant in policy.grants:
                if fnmatch(secret_ref, grant.secret_ref) or secret_ref == grant.secret_ref:
                    return grant, policy

        # Deny by default — no matching policy
        return None, None

    def evaluate_all_grants(
        self,
        requester: str,
        environment: str,
        task: str,
    ) -> list[tuple[Grant, Policy]]:
        """Return all grants available for a given request context."""
        results: list[tuple[Grant, Policy]] = []
        for policy in self.policies:
            if policy.deny:
                continue
            if not self._conditions_match(policy, requester, environment, task):
                continue
            for grant in policy.grants:
                results.append((grant, policy))
        return results

    @staticmethod
    def _conditions_match(
        policy: Policy, requester: str, environment: str, task: str
    ) -> bool:
        return any(
            fnmatch(requester, c.requester)
            and fnmatch(environment, c.environment)
            and fnmatch(task, c.task)
            for c in policy.conditions
        )
