from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import click

from backend.config import settings


def _ref_to_env_var(secret_ref: str) -> str:
    """Convert op://vault/item/field to ITEM_FIELD."""
    parts = secret_ref.replace("op://", "").replace("ssh://", "").split("/")
    if len(parts) >= 3:
        name = f"{parts[1]}_{parts[2]}"
    elif len(parts) >= 2:
        name = parts[1]
    else:
        name = parts[0]
    return name.upper().replace("-", "_")


async def _run_with_secrets(task: str, env: str, requester: str, command: tuple[str, ...]) -> int:
    from backend.policy.engine import PolicyEngine
    from backend.secrets.factory import create_secret_provider
    from backend.audit.logger import log_event

    engine = PolicyEngine(settings.policy_dir)
    provider = create_secret_provider()

    grants = engine.evaluate_all_grants(requester, env, task)

    if not grants:
        click.echo(click.style("DENIED", fg="red") + f" — no policy grants for {requester} in {env}/{task}")
        return 1

    # Build subprocess environment
    child_env = os.environ.copy()
    resolved: list[tuple[str, str, str]] = []  # (ref, env_var, policy_name)

    for grant, policy in grants:
        try:
            value = await provider.resolve(grant.secret_ref)
            var_name = _ref_to_env_var(grant.secret_ref)
            child_env[var_name] = value
            resolved.append((grant.secret_ref, var_name, policy.name))
            click.echo(
                click.style("GRANTED", fg="green")
                + f" — {grant.secret_ref} → ${var_name} (TTL: {grant.ttl_seconds}s, policy: {policy.name})"
            )
        except Exception as exc:
            click.echo(click.style("ERROR", fg="red") + f" — Failed to resolve {grant.secret_ref}: {exc}")

    if not resolved:
        click.echo(click.style("ERROR", fg="red") + " — No secrets resolved successfully")
        return 1

    # Log grant events
    from backend.database import init_db
    await init_db()

    for ref, var, pol in resolved:
        await log_event(
            requester=requester, environment=env, task=task,
            secret_ref=ref, action="granted", policy_name=pol,
        )

    # Spawn the subprocess
    click.echo(f"\n→ Running: {' '.join(command)}\n")
    result = subprocess.run(list(command), env=child_env)

    # Log release events and clear secrets
    for ref, var, pol in resolved:
        child_env.pop(var, None)
        await log_event(
            requester=requester, environment=env, task=task,
            secret_ref=ref, action="released", policy_name=pol,
        )

    click.echo(f"\n→ Process exited with code {result.returncode}. Secrets cleared.")
    return result.returncode


@click.command()
@click.option("--task", required=True, help="Task context for policy evaluation")
@click.option("--env", "environment", default="development", help="Environment (development/staging/production)")
@click.option("--requester", default=None, help="Requester identity (default: user:<login>)")
@click.argument("command", nargs=-1, required=True)
def run_cmd(task: str, environment: str, requester: str | None, command: tuple[str, ...]):
    """Run a command with policy-scoped secrets injected into its environment."""
    if requester is None:
        requester = f"user:{os.getlogin()}"

    exit_code = asyncio.run(_run_with_secrets(task, environment, requester, command))
    sys.exit(exit_code)
