from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import typer

from spendtop import __version__

app = typer.Typer(
    name="spendtop",
    help="Local-first terminal dashboard for AI coding tool spend.",
    no_args_is_help=False,
)
connect_app = typer.Typer(help="Configure connector credentials.")
app.add_typer(connect_app, name="connect")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"spendtop {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Local-first TUI for AI coding tool spend. Run with no args to launch the dashboard."""
    if ctx.invoked_subcommand is None and not version:
        _launch_tui()


def _build_connectors() -> list:
    from spendtop.connectors.spend.anthropic import AnthropicConnector
    from spendtop.connectors.spend.openai import OpenAIConnector
    from spendtop.core.config import load_config

    cfg = load_config()
    connectors = []
    if cfg.anthropic.enabled:
        connectors.append(AnthropicConnector(cfg.anthropic.credential()))
    if cfg.openai.enabled:
        connectors.append(OpenAIConnector(cfg.openai.credential()))
    return connectors


def _launch_tui() -> None:
    from spendtop.core.cache import init_db, latest_ts
    from spendtop.tui.app import SpendTopApp

    init_db()
    connectors = _build_connectors()

    # Auto-pull if cache is stale (no data in last 4 hours)
    stale = True
    for c in connectors:
        ts = latest_ts(c.name)
        if ts and (datetime.now(tz=UTC) - ts) < timedelta(hours=4):
            stale = False
            break

    if stale and any(c.status() != "unconfigured" for c in connectors):
        typer.echo("Cache stale — pulling fresh data…")
        asyncio.run(_pull_all(connectors, days=30))

    SpendTopApp(connectors=connectors).run()


@app.command()
def pull(
    days: int = typer.Option(30, "--days", "-d", help="How many days back to pull."),
) -> None:
    """Pull spend data from all enabled connectors into the local cache."""
    from spendtop.core.cache import init_db

    init_db()
    connectors = _build_connectors()
    configured = [c for c in connectors if c.status() != "unconfigured"]
    if not configured:
        typer.echo(
            "No connectors configured. "
            "Run 'spendtop connect anthropic' or 'spendtop connect openai'."
        )
        raise typer.Exit(1)

    typer.echo(f"Pulling {days} days from {len(configured)} connector(s)…")
    inserted = asyncio.run(_pull_all(configured, days=days))
    typer.echo(f"Done. {inserted} new event(s) upserted.")


async def _pull_all(connectors: list, days: int) -> int:
    from spendtop.core.cache import upsert_spend

    since = datetime.now(tz=UTC) - timedelta(days=days)
    total = 0
    for connector in connectors:
        try:
            events = await connector.pull(since)
            n = upsert_spend(events)
            typer.echo(f"  {connector.name}: {n} new event(s)")
            total += n
        except Exception as exc:
            typer.echo(f"  {connector.name}: ERROR — {exc}", err=True)
    return total


@connect_app.command("anthropic")
def connect_anthropic() -> None:
    """Store an Anthropic Admin API key in the system keyring."""
    from spendtop.core.config import store_credential

    key = typer.prompt("Anthropic Admin API key", hide_input=True)
    if not key.startswith("sk-ant-admin"):
        typer.echo("Warning: key doesn't look like an admin key (expected sk-ant-admin…)")
    store_credential("anthropic", key)
    typer.echo("Stored in keyring under 'spendtop:anthropic'. Run 'spendtop pull' to test it.")


@connect_app.command("openai")
def connect_openai() -> None:
    """Store an OpenAI Admin API key in the system keyring."""
    from spendtop.core.config import store_credential

    key = typer.prompt("OpenAI Admin API key", hide_input=True)
    store_credential("openai", key)
    typer.echo("Stored in keyring under 'spendtop:openai'. Run 'spendtop pull' to test it.")
