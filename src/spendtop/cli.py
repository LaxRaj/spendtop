from __future__ import annotations

import typer

from spendtop import __version__

app = typer.Typer(
    name="spendtop",
    help="Local-first terminal dashboard for AI coding tool spend.",
    no_args_is_help=False,
)


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
        typer.echo("spendtop: run 'spendtop --help' for usage. (TUI coming in Stage 1)")
