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
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from forge.cli.exit_codes import ExitCode, exit_code_for
from forge.domain.errors import ForgeError
from forge.domain.source import AnalysisResult
from forge.presentation.findings import render_plain, render_rich

Analyze = Callable[[Path], AnalysisResult]
"""What the command needs: something that turns a path into a result.

Typed as a callable rather than as ``AnalyzeSourceFile`` so the composition
root can pass a wrapper that defers loading configuration until a command
actually runs - without the command knowing or caring.
"""

HELP = """\
Analyse a source file and report likely defects.

Reads the file, sends it to the configured AI provider, and prints what it \
finds. Forge never modifies the file and never runs it.

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
) -> ExitCode:
    """Run the analysis and print it. Returns the exit code, never raises.

    Args:
        analyze: The use case, already wired with its adapters.
        path: The file to analyse.
        plain: Force plain output. Otherwise the choice is made from whether
            stdout is a terminal, so a piped run is readable without the caller
            having to remember a flag.
    """
    try:
        result = analyze(path)
    except ForgeError as error:
        # Diagnostics go to stderr so that a piped stdout carries results only.
        print(f"forge: {error}", file=sys.stderr)
        return exit_code_for(error)

    use_plain = plain or not sys.stdout.isatty()
    print(render_plain(result) if use_plain else render_rich(result), end="")
    return ExitCode.OK


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
    ) -> None:
        raise typer.Exit(code=debug(analyze, path, plain=plain))
