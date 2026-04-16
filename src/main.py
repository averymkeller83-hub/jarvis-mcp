import click
import uvicorn


@click.group()
def cli() -> None:
    """JARVIS MCP — AI assistant server."""


@cli.command()
@click.option("--host", default="127.0.0.1", help="Bind address.")
@click.option("--port", default=7900, type=int, help="Bind port.")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development.")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the JARVIS MCP server."""
    uvicorn.run("src.server.app:app", host=host, port=port, reload=reload)


@cli.command()
def setup() -> None:
    """Run first-time setup."""
    click.echo("Setup complete.")


@cli.command()
def uninstall() -> None:
    """Remove JARVIS MCP configuration and services."""
    click.echo("Uninstalled.")


if __name__ == "__main__":
    cli()
