"""The human-confirmed `forge review` command."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from forge.application.review import ReviewChanges
from forge.cli.exit_codes import ExitCode, exit_code_for
from forge.domain.errors import ForgeError
from forge.presentation.review import render_review_plan, render_review_result

HELP = """\
Review the current Git changes with one bounded AI request.

Shows the paths, omissions, model, and estimated request size before asking
for consent. A non-interactive run prints the plan and makes no provider call.
Requires a configured provider and API key.
Forge never modifies files, runs project commands, or guarantees complete
coverage. Suspected secrets stop the review before any provider call.
"""

ReviewFactory = Callable[[], ReviewChanges]


def review(factory: ReviewFactory, paths: tuple[Path, ...] = ()) -> ExitCode:
    """Prepare, show, confirm, and complete a single bounded review."""
    try:
        use_case = factory()
        plan = use_case.prepare(paths)
    except ForgeError as error:
        print(f"forge: {_safe_diagnostic(str(error))}", file=sys.stderr)
        return exit_code_for(error)

    print(render_review_plan(plan), end="")
    if plan.request is None:
        return ExitCode.FAILED
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "forge: No review was sent because confirmation requires an "
            "interactive terminal.",
            file=sys.stderr,
        )
        return ExitCode.FAILED
    if not typer.confirm("Send this source to the configured provider?", default=False):
        return ExitCode.OK

    try:
        if sys.stderr.isatty():
            with Console(stderr=True).status("Reviewing changes...", spinner="dots"):
                result = use_case.complete(plan)
        else:
            result = use_case.complete(plan)
    except ForgeError as error:
        print(f"forge: {_safe_diagnostic(str(error))}", file=sys.stderr)
        return exit_code_for(error)
    print(render_review_result(result), end="")
    return ExitCode.OK


def _safe_diagnostic(message: str) -> str:
    """Escape terminal controls in diagnostics that may contain Git paths."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode()
        for char in message
    )


def register(app: typer.Typer, factory: ReviewFactory) -> None:
    """Attach the Git change review with an API-free help surface."""

    @app.command("review", help=HELP)
    def _run(
        paths: Annotated[
            list[Path] | None,
            typer.Argument(
                metavar="PATH...",
                help="Optional changed paths to narrow the default review scope.",
                show_default=False,
            ),
        ] = None,
    ) -> None:
        code = review(factory, tuple(paths or ()))
        raise typer.Exit(code=code)
