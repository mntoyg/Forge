"""Composition root for the Forge CLI.

This module is the only place allowed to know about every layer at once: it
builds the Typer application and, in the future, wires concrete infrastructure
adapters into application use cases. Keep it thin - it holds wiring, never
business logic.
"""

from typing import Annotated

import typer
from rich.console import Console

from forge import __version__

app = typer.Typer(
    name="forge",
    help="Forge - an AI-first coding assistant for the terminal.",
    no_args_is_help=True,
    add_completion=False,
)

_console = Console()


def _version_callback(value: bool) -> None:
    """Print the version and exit, so ``--version`` short-circuits the app."""
    if value:
        _console.print(f"forge {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show the Forge version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Root callback.

    Commands are registered here as capabilities land. The repository is
    currently at the foundation stage: no feature commands exist yet, and
    ``forge debug`` is deliberately not implemented.
    """


if __name__ == "__main__":  # pragma: no cover - manual entry point
    app()
