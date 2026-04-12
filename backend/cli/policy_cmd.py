from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from backend.config import settings


@click.group()
def policy_cmd():
    """Manage and inspect policies."""
    pass


@policy_cmd.command("list")
def list_policies():
    """List all loaded policies."""
    from backend.policy.loader import load_policies_from_directory

    policies = load_policies_from_directory(settings.policy_dir)
    console = Console()

    table = Table(title="AgentGate Policies")
    table.add_column("Priority", style="cyan", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("Type", style="magenta")
    table.add_column("Conditions")
    table.add_column("Grants")

    for p in policies:
        conds = "; ".join(
            f"{c.requester}@{c.environment}/{c.task}" for c in p.conditions
        )
        grants = "; ".join(g.secret_ref for g in p.grants) if not p.deny else "-"
        table.add_row(
            str(p.priority),
            p.name,
            click.style("DENY", fg="red") if p.deny else click.style("ALLOW", fg="green"),
            conds,
            grants,
        )

    console.print(table)


@policy_cmd.command("validate")
def validate_policies():
    """Validate all policy files for syntax errors."""
    from backend.policy.loader import load_policies_from_directory
    from pathlib import Path

    path = Path(settings.policy_dir)
    if not path.exists():
        click.echo(click.style("ERROR", fg="red") + f" - Policy directory not found: {path}")
        return

    try:
        policies = load_policies_from_directory(path)
        click.echo(click.style("OK", fg="green") + f" - {len(policies)} policies loaded successfully")
        for p in policies:
            icon = "DENY:" if p.deny else "  OK:"
            click.echo(f"  {icon} {p.name} (priority={p.priority})")
    except ValueError as exc:
        click.echo(click.style("ERROR", fg="red") + f" - {exc}")
