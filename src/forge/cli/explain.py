"""The single-file `forge explain` command."""

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from forge.application.explain import ExplainSource
from forge.cli.exit_codes import ExitCode, exit_code_for
from forge.domain.errors import ForgeError
from forge.presentation.explanation import render_explanation

HELP = """\
Explain one source file using the configured AI provider.

The selected file is sent to the provider in one request. Forge does not inspect
other files, run commands, or modify files. Claims cite the supplied source,
but the AI explanation may be incomplete or wrong.
"""

ExplainFactory = Callable[[], ExplainSource]


def explain(factory: ExplainFactory, path: Path, *, plain: bool = False) -> ExitCode:
    """Read, explain, and render one selected file with no confirmation loop."""
    try:
        use_case = factory()
        with _waiting(path, plain):
            result = use_case(path)
    except ForgeError as error:
        print(f"forge: {_safe_diagnostic(str(error))}", file=sys.stderr)
        return exit_code_for(error)

    # The explanation renderer is intentionally plain text, including in a
    # terminal. This keeps model and source text from being interpreted as markup.
    sys.stdout.write(render_explanation(result))
    return ExitCode.OK


@contextmanager
def _waiting(path: Path, plain: bool) -> Iterator[None]:
    if plain or not sys.stderr.isatty():
        yield
        return
    with Console(stderr=True).status(f"Explaining {path.name}...", spinner="dots"):
        yield


def _safe_diagnostic(message: str) -> str:
    """Escape terminal controls in diagnostics that may include a user path."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode()
        for char in message
    )


def register(app: typer.Typer, factory: ExplainFactory) -> None:
    """Register the command without loading configuration during help output."""

    @app.command("explain", help=HELP)
    def _run(
        path: Annotated[
            Path,
            typer.Argument(
                metavar="FILE",
                help="Path to one source file inside the current workspace.",
                show_default=False,
            ),
        ],
        plain: Annotated[
            bool,
            typer.Option(
                "--plain",
                help="Disable the progress spinner and keep output plain.",
            ),
        ] = False,
    ) -> None:
        raise typer.Exit(code=explain(factory, path, plain=plain))
