from __future__ import annotations

import click


@click.group()
@click.version_option(version="0.1.0", prog_name="agentgate")
def cli():
    """AgentGate — Runtime Credential Broker for AI Agents."""
    pass


# Import and register subcommands
from backend.cli.run import run_cmd
from backend.cli.policy_cmd import policy_cmd
from backend.cli.audit_cmd import audit_cmd
from backend.cli.server_cmd import server_cmd

cli.add_command(run_cmd, "run")
cli.add_command(policy_cmd, "policy")
cli.add_command(audit_cmd, "audit")
cli.add_command(server_cmd, "server")


if __name__ == "__main__":
    cli()
