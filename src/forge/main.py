"""Composition root for the Forge CLI.

This module is the only place allowed to know about every layer at once: it
builds the Typer application and wires concrete infrastructure adapters into
application use cases. Keep it thin - it holds wiring, never business logic.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from forge import __version__
from forge.application.analyze import AnalyzeSourceFile
from forge.application.explain import ExplainSource
from forge.application.inspect import InspectProject
from forge.application.review import ReviewChanges
from forge.cli import debug as debug_cli
from forge.cli import explain as explain_cli
from forge.cli import inspect as inspect_cli
from forge.cli import review as review_cli
from forge.domain.source import AnalysisResult
from forge.infrastructure.change_set import GitChangeSetReader
from forge.infrastructure.config import Settings, load_settings
from forge.infrastructure.logging import configure_logging
from forge.infrastructure.openai_provider import OpenAIProvider
from forge.infrastructure.project import FilesystemProjectEvidenceReader
from forge.infrastructure.repository import GitRepositoryInspector
from forge.infrastructure.source import FilesystemSourceReader

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
    """Root callback. Commands are registered at import time, below."""


def build_analyzer(settings: Settings) -> AnalyzeSourceFile:
    """Wire the concrete adapters into the analyse use case.

    The workspace is the current working directory: Forge reads what you point
    it at, from where you are standing. Enforcing that is the reader's job, not
    this function's - wiring decides *which* adapter, never what it permits.
    """
    workspace = Path.cwd()
    reader = FilesystemSourceReader(workspace, max_bytes=settings.max_file_bytes)
    provider = OpenAIProvider(
        api_key=settings.require_api_key(),
        model=settings.model,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout_seconds,
    )
    # The inspector is always wired, and always cheap: it opens no repository
    # until a command asks it something. A user outside version control keeps
    # every part of `forge debug` except --diff.
    inspector = GitRepositoryInspector(workspace)
    return AnalyzeSourceFile(reader, provider, inspector)


def _analyze(path: Path, *, changes_only: bool = False) -> AnalysisResult:
    """Build the use case on demand, then run it.

    Configuration is loaded here rather than at import time so that
    ``forge --version`` and ``forge --help`` work on a machine with no API key.
    Loading eagerly would make the help text require a credential, which is a
    poor first impression and an unnecessary one.

    Logging is configured with the key registered as a secret, so that the
    redacting sink knows what to hide before anything is written.
    """
    settings = load_settings()
    configure_logging(
        settings.log_level,
        secrets=[settings.api_key.get_secret_value()] if settings.api_key else [],
    )
    return build_analyzer(settings)(path, changes_only=changes_only)


def _review_factory() -> ReviewChanges:
    """Build review adapters on command invocation, never during help output."""
    settings = load_settings()
    configure_logging(
        settings.log_level,
        secrets=[settings.api_key.get_secret_value()] if settings.api_key else [],
    )
    workspace = Path.cwd()
    provider = OpenAIProvider(
        api_key=settings.require_api_key(),
        model=settings.model,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout_seconds,
    )
    return ReviewChanges(GitChangeSetReader(workspace), provider, model=settings.model)


def _explain_factory() -> ExplainSource:
    """Build the single-file explanation use case only when invoked."""
    settings = load_settings()
    configure_logging(
        settings.log_level,
        secrets=[settings.api_key.get_secret_value()] if settings.api_key else [],
    )
    workspace = Path.cwd()
    reader = FilesystemSourceReader(workspace, max_bytes=settings.max_file_bytes)
    provider = OpenAIProvider(
        api_key=settings.require_api_key(),
        model=settings.model,
        base_url=settings.base_url,
        timeout_seconds=settings.timeout_seconds,
    )
    return ExplainSource(reader, provider)


debug_cli.register(app, _analyze)
explain_cli.register(app, _explain_factory)
inspect_cli.register(app, InspectProject(FilesystemProjectEvidenceReader()))
review_cli.register(app, _review_factory)


if __name__ == "__main__":  # pragma: no cover - manual entry point
    app()
