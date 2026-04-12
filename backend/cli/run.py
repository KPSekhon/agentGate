from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import click

from backend.config import settings


def _ref_to_env_var(secret_ref: str) -> str:
    """Fallback: convert op://vault/item/field to ITEM_FIELD."""
    parts = secret_ref.replace("op://", "").replace("ssh://", "").split("/")
    if len(parts) >= 3:
        name = f"{parts[1]}_{parts[2]}"
    elif len(parts) >= 2:
        name = parts[1]
    else:
        name = parts[0]
    return name.upper().replace("-", "_")


async def _run_with_secrets(
    task: str,
    env: str,
    requester: str,
    command: tuple[str, ...],
    secret_args: tuple[str, ...],
) -> int:
    from backend.policy.engine import PolicyEngine
    from backend.secrets.factory import create_secret_provider
    from backend.audit.logger import log_event
    from backend.project_config import load_project_config

    engine = PolicyEngine(settings.policy_dir)
    provider = create_secret_provider()

    # Determine secrets to inject. Priority:
    # 1. Explicit --secret flags (REF=ENV_VAR or just REF)
    # 2. .agentgate.yaml project config
    # 3. Fall back to all grants from matching policies
    secret_mappings: list[tuple[str, str]] = []  # (ref, env_var_name)

    if secret_args:
        for arg in secret_args:
            if "=" in arg:
                ref, var = arg.split("=", 1)
                secret_mappings.append((ref.strip(), var.strip()))
            else:
                secret_mappings.append((arg.strip(), _ref_to_env_var(arg.strip())))
    else:
        project = load_project_config()
        if project and project.secrets:
            for s in project.secrets:
                secret_mappings.append((s.ref, s.env_var))
            # Use project config defaults if not overridden
            if task == "default" and project.task != "default":
                task = project.task
            if env == "development" and project.environment != "development":
                env = project.environment
            click.echo(f"Using .agentgate.yaml ({len(project.secrets)} secrets mapped)")

    # If still no explicit mappings, discover from policy grants
    if not secret_mappings:
        grants = engine.evaluate_all_grants(requester, env, task)
        if not grants:
            click.echo(
                click.style("DENIED", fg="red")
                + f" -- no policy grants for {requester} in {env}/{task}. "
                + "Define a policy or create a .agentgate.yaml file."
            )
            return 1
        for grant, policy in grants:
            secret_mappings.append((grant.secret_ref, _ref_to_env_var(grant.secret_ref)))

    # Validate each secret against policy before resolving
    child_env = os.environ.copy()
    resolved: list[tuple[str, str, str]] = []  # (ref, env_var, policy_name)

    for ref, var_name in secret_mappings:
        grant, policy = engine.evaluate(requester, env, task, ref)
        if grant is None:
            if policy and policy.deny:
                click.echo(
                    click.style("DENIED", fg="red")
                    + f" -- {ref}: blocked by policy '{policy.name}'"
                )
            else:
                click.echo(
                    click.style("DENIED", fg="red")
                    + f" -- {ref}: no matching policy for {requester} in {env}/{task}"
                )
            continue

        try:
            value = await provider.resolve(ref)
            child_env[var_name] = value
            resolved.append((ref, var_name, policy.name))
            click.echo(
                click.style("GRANTED", fg="green")
                + f" -- {ref} -> ${var_name} (TTL: {grant.ttl_seconds}s, policy: {policy.name})"
            )
        except Exception as exc:
            click.echo(click.style("ERROR", fg="red") + f" -- Failed to resolve {ref}: {exc}")

    if not resolved:
        click.echo(click.style("ERROR", fg="red") + " -- No secrets resolved. Aborting.")
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
    click.echo(f"\n> Running: {' '.join(command)}\n")
    result = subprocess.run(list(command), env=child_env)

    # Log release events and clear secrets from memory
    for ref, var, pol in resolved:
        child_env.pop(var, None)
        await log_event(
            requester=requester, environment=env, task=task,
            secret_ref=ref, action="released", policy_name=pol,
        )

    click.echo(f"\n> Process exited with code {result.returncode}. Secrets cleared.")
    return result.returncode


@click.command()
@click.option("--task", default="default", help="Task context for policy evaluation")
@click.option("--env", "environment", default="development", help="Environment (development/staging/production)")
@click.option("--requester", default=None, help="Requester identity (default: user:<login>)")
@click.option(
    "--secret", "secrets", multiple=True,
    help="Secret to inject. Format: REF=ENV_VAR or just REF. Can be repeated. "
         "Example: --secret 'op://vault/key/cred=API_KEY'"
)
@click.argument("command", nargs=-1, required=True)
def run_cmd(task: str, environment: str, requester: str | None, secrets: tuple[str, ...], command: tuple[str, ...]):
    """Run a command with policy-scoped secrets injected into its environment.

    Secrets are determined by (in priority order):
    1. Explicit --secret flags
    2. .agentgate.yaml project config file
    3. All grants from matching policies
    """
    if requester is None:
        try:
            requester = f"user:{os.getlogin()}"
        except OSError:
            requester = "user:unknown"

    exit_code = asyncio.run(_run_with_secrets(task, environment, requester, command, secrets))
    sys.exit(exit_code)
