from __future__ import annotations

import asyncio

import click
from rich.console import Console
from rich.table import Table


@click.group()
def audit_cmd():
    """View audit logs."""
    pass


@audit_cmd.command("tail")
@click.option("--limit", default=20, help="Number of recent entries")
@click.option("--action", default=None, help="Filter by action (granted/denied/released/expired)")
def tail_logs(limit: int, action: str | None):
    """Show recent audit log entries."""
    asyncio.run(_tail(limit, action))


async def _tail(limit: int, action: str | None):
    from backend.database import init_db
    from backend.audit.logger import get_logs

    await init_db()
    logs = await get_logs(limit=limit, action=action)

    console = Console()
    table = Table(title="Recent Audit Logs")
    table.add_column("Time", style="dim")
    table.add_column("Action", style="bold")
    table.add_column("Requester")
    table.add_column("Secret Ref")
    table.add_column("Policy")
    table.add_column("Anomaly", justify="right")

    for entry in logs:
        action_style = {
            "granted": "green",
            "denied": "red",
            "released": "blue",
            "expired": "yellow",
        }.get(entry.action, "white")

        anomaly_str = f"{entry.anomaly_score:.1f}"
        anomaly_style = "bold red" if entry.anomaly_score > 0.5 else "dim"

        table.add_row(
            entry.timestamp.strftime("%H:%M:%S"),
            click.style(entry.action.upper(), fg=action_style),
            entry.requester,
            entry.secret_ref,
            entry.policy_name or "-",
            f"[{anomaly_style}]{anomaly_str}[/{anomaly_style}]",
        )

    console.print(table)
