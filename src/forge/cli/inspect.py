"""CLI surface for deterministic project inspection."""

import sys
from pathlib import Path
from typing import Annotated

import typer

from forge.application.inspect import InspectProject
from forge.cli.exit_codes import exit_code_for
from forge.domain.errors import ForgeError
from forge.presentation.project import render_project_overview


def register(app: typer.Typer, inspect: InspectProject) -> None:
    """Register the project overview command with its use case wired in."""

    @app.command("inspect", help="Show a local, evidence-based project overview.")
    def _run(
        directory: Annotated[
            Path,
            typer.Argument(
                metavar="DIRECTORY",
                help="Project directory to inspect (defaults to the current directory).",
                show_default=False,
            ),
        ] = Path(),
    ) -> None:
        try:
            overview = inspect(directory)
        except ForgeError as error:
            print(f"forge: {error}", file=sys.stderr)
            raise typer.Exit(code=exit_code_for(error)) from error
        print(render_project_overview(overview), end="")
