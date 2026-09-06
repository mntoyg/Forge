"""The `forge debug` command.

Thin by design. It parses one argument, calls one use case, hands the result to
a renderer, and maps an error to an exit code. If this file starts making
decisions about *what* an analysis means, that logic has leaked out of the
application layer.

It takes its use case as a parameter rather than building one, so that an
end-to-end test can drive the real command surface against fakes - no network,
no key, no filesystem beyond a temporary directory.
"""

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from forge.cli.exit_codes import ExitCode, exit_code_for
from forge.domain.errors import ForgeError
from forge.domain.source import AnalysisResult
from forge.presentation.findings import render_plain, render_rich

Analyze = Callable[..., AnalysisResult]
"""What the command needs: something that turns a path into a result.

Typed as a callable rather than as ``AnalyzeSourceFile`` so the composition
root can pass a wrapper that defers loading configuration until a command
actually runs - without the command knowing or caring.
"""

WAITING = "Analysing {name}"
"""What the spinner says while the provider is thinking.

Named rather than inlined so a test can assert on the source string instead of
on rendered terminal output, which wraps to whatever width happens to be there.
"""

HELP = """\
Analyse a source file and report likely defects.

Reads the file, sends it to the configured AI provider, and prints what it \
finds. Forge never modifies the file and never runs it.

With --diff, only the lines you have changed since the last commit are \
reviewed. The whole file is still sent, because a change cannot be judged \
without the code around it - so --diff narrows the answer rather than the \
bill.

Findings do not change the exit code: a file with twenty problems still exits \
0, because the command succeeded. Exit codes report whether Forge worked, not \
whether your code is good.

  0  analysis completed          3  not configured
  1  could not produce a result  4  provider failed
  2  unusable input
"""


def debug(
    analyze: Analyze,
    path: Path,
    *,
    plain: bool = False,
    changes_only: bool = False,
) -> ExitCode:
    """Run the analysis and print it. Returns the exit code, never raises.

    Args:
        analyze: The use case, already wired with its adapters.
        path: The file to analyse.
        plain: Force plain output. Otherwise the choice is made from whether
            stdout is a terminal, so a piped run is readable without the caller
            having to remember a flag.
        changes_only: Review only the lines with uncommitted changes.
    """
    try:
        with _waiting(_progress_console(plain), path):
            result = analyze(path, changes_only=changes_only)
    except ForgeError as error:
        # Diagnostics go to stderr so that a piped stdout carries results only.
        print(f"forge: {error}", file=sys.stderr)
        return exit_code_for(error)

    use_plain = plain or not sys.stdout.isatty()
    print(render_plain(result) if use_plain else render_rich(result), end="")
    return ExitCode.OK


def _progress_console(plain: bool) -> Console | None:
    """Where the spinner should be drawn, or ``None`` if it should not be.

    It is drawn on **stderr**, which is the same rule the diagnostics follow: a
    piped stdout carries results and nothing else. And it is skipped entirely
    when stderr is not a terminal, or when plain output was asked for, because
    a spinner in a log file is a line of escape codes nobody wanted.
    """
    if plain or not sys.stderr.isatty():
        return None
    return Console(stderr=True)


@contextmanager
def _waiting(console: Console | None, path: Path) -> Iterator[None]:
    """Show that something is happening while the provider thinks.

    NFR-3.2. A provider call takes seconds, and a terminal that has printed
    nothing for that long is indistinguishable from one that has hung - the
    user's next move is Ctrl-C, on a call they have already paid for.

    The console is passed in rather than built here so that the decision about
    *whether* to draw one stays in :func:`_progress_console`, where it can be
    read and tested on its own.
    """
    if console is None:
        yield
        return

    with console.status(WAITING.format(name=path.name), spinner="dots"):
        yield


def register(app: typer.Typer, analyze: Analyze) -> None:
    """Attach the command to ``app`` with its dependency already bound.

    The Typer signature lives here rather than on :func:`debug` so that the
    function above stays a plain, directly testable callable.
    """

    # The command name is given explicitly. Typer would otherwise derive it
    # from the function name, and the inner function cannot be called `debug`
    # without shadowing the module-level one it delegates to.
    @app.command("debug", help=HELP)
    def _run(
        path: Annotated[
            Path,
            typer.Argument(
                metavar="FILE",
                help="Path to the source file to analyse.",
                show_default=False,
            ),
        ],
        plain: Annotated[
            bool,
            typer.Option(
                "--plain",
                help="Plain text output, even in a terminal.",
            ),
        ] = False,
        diff: Annotated[
            bool,
            typer.Option(
                "--diff",
                help="Review only the lines changed since the last commit.",
            ),
        ] = False,
    ) -> None:
        raise typer.Exit(code=debug(analyze, path, plain=plain, changes_only=diff))
