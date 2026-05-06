"""Typer CLI."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from agentlog.db import init_db
from agentlog.seed import seed as seed_db

load_dotenv()

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def init():
    asyncio.run(init_db())
    console.print("[green]DB initialized.[/]")


@app.command()
def seed(n: int = typer.Option(60, "--n", help="Number of synthetic runs")):
    db = Path("agentlog.db")
    if db.exists():
        db.unlink()
        console.print("[dim]Removed existing agentlog.db[/]")
    asyncio.run(seed_db(n))
    console.print(f"[green]Seeded {n} runs.[/]")


@app.command()
def serve(
    host: str = os.environ.get("AGENTLOG_HOST", "0.0.0.0"),
    port: int = int(os.environ.get("AGENTLOG_PORT", "8090")),
):
    """Run the FastAPI dashboard."""
    import uvicorn

    uvicorn.run("agentlog.api:app", host=host, port=port, reload=False)


@app.command()
def version():
    from agentlog import __version__
    console.print(f"observability-dashboard {__version__}")


if __name__ == "__main__":
    app()
