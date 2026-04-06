from __future__ import annotations

import click

from backend.config import settings


@click.command()
@click.option("--host", default=None, help="Bind host")
@click.option("--port", default=None, type=int, help="Bind port")
def server_cmd(host: str | None, port: int | None):
    """Start the AgentGate API server."""
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
