"""The single-file `forge explain` command."""

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console

from forge.application.explain import ExplainSource
from forge.cli.exit_codes import ExitCode, exit_code_for
from forge.cli.output import write_json_error_line, write_json_line
from forge.domain.errors import (
    ForgeError,
    PathOutsideWorkspaceError,
    SourceUnreadableError,
)
from forge.presentation.explanation import render_explanation
from forge.presentation.json_output import (
    JsonCommand,
    serialize_explanation_json,
)

HELP = """\
Explain one source file using the configured AI provider.

The selected file is sent to the provider in one request. Forge does not inspect
other files, run commands, or modify files. Claims cite the supplied source,
but the AI explanation may be incomplete or wrong.
"""

ExplainFactory = Callable[[], ExplainSource]


def explain(
    factory: ExplainFactory,
    path: Path,
    *,
    plain: bool = False,
    output_format: Literal["text", "json"] = "text",
) -> ExitCode:
    """Read, explain, and render one selected file with no confirmation loop."""
    try:
        safe_path = (
            _safe_relative_source_path(path) if output_format == "json" else None
        )
        use_case = factory()
        with _waiting(path, plain or output_format == "json"):
            result = use_case(path)
    except ForgeError as error:
        code = exit_code_for(error)
        if output_format == "json":
            write_json_error_line(JsonCommand.EXPLAIN, code)
        else:
            print(f"forge: {_safe_diagnostic(str(error))}", file=sys.stderr)
        return code

    if output_format == "json":
        if safe_path is None:
            raise RuntimeError("JSON mode requires a validated source path.")
        write_json_line(serialize_explanation_json(result, safe_path))
        return ExitCode.OK

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


def _safe_relative_source_path(path: Path) -> str:
    """Resolve a selected source to a safe path relative to the invocation workspace."""
    try:
        workspace = Path.cwd().resolve()
        selected = path.resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise SourceUnreadableError(
            "The selected path could not be resolved inside the workspace."
        ) from error

    try:
        relative = selected.relative_to(workspace)
    except ValueError as error:
        raise PathOutsideWorkspaceError(
            "The selected path is outside the current workspace."
        ) from error

    safe_path = relative.as_posix()
    if not relative.parts or safe_path in {"", "."} or ".." in relative.parts:
        raise SourceUnreadableError(
            "The selected path does not identify a file inside the workspace."
        )
    return safe_path


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
        output_format: Annotated[
            Literal["text", "json"],
            typer.Option("--format", help="Output format: text or json."),
        ] = "text",
    ) -> None:
        raise typer.Exit(
            code=explain(factory, path, plain=plain, output_format=output_format)
        )
