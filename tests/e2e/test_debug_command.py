"""`forge debug`, driven the way a user drives it.

The command is exercised through the real Typer surface, with the use case
replaced by a fake. That keeps every test offline and free while still going
through argument parsing, rendering, and exit-code mapping - the three things
only an end-to-end test covers.

ADR-0006 says an exit code without a test is an intention, not a contract.
There is therefore one test per code.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from forge.application.analyze import AnalyzeSourceFile
from forge.cli import debug as debug_cli
from forge.cli.exit_codes import ExitCode
from forge.domain.ai import CompletionResponse, TokenUsage
from forge.domain.errors import (
    ConfigurationError,
    PathOutsideWorkspaceError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    SourceNotFoundError,
    SourceTooLargeError,
)
from forge.domain.source import SourceFile
from tests.support.fakes import FakeProvider, FakeSourceReader

runner = CliRunner()

SOURCE = SourceFile(path=Path("app.py"), content="a = 1\nb = 2\nc = 3\n")

FINDINGS = [
    {
        "summary": "Divides without guarding zero",
        "detail": "An empty list raises ZeroDivisionError.",
        "severity": "high",
        "confidence": "certain",
        "line": 2,
    },
    {
        "summary": "Off-by-one in the slice",
        "detail": "Returns one item fewer than asked for.",
        "severity": "medium",
        "confidence": "likely",
        "line": 3,
    },
]


def _app(analyze: Callable[[Path], object]) -> typer.Typer:
    """Build a one-command app around ``analyze``."""
    app = typer.Typer()
    debug_cli.register(app, analyze)  # type: ignore[arg-type]
    return app


def _analyzing(*findings: object) -> Callable[[Path], object]:
    return AnalyzeSourceFile(
        FakeSourceReader(source=SOURCE),
        FakeProvider(
            response=CompletionResponse(
                text=json.dumps({"findings": list(findings)}),
                model="fake-model",
                usage=TokenUsage(input_tokens=120, output_tokens=45),
            )
        ),
    )


def _failing(error: Exception) -> Callable[[Path], object]:
    def analyze(path: Path) -> object:
        raise error

    return analyze


# --- exit code 0: the command did what was asked ---------------------------


@pytest.mark.e2e
def test_findings_are_reported_and_still_exit_zero() -> None:
    """ADR-0006: findings mean the tool worked, not that the build should fail."""
    result = runner.invoke(_app(_analyzing(*FINDINGS)), ["app.py"])

    assert result.exit_code == ExitCode.OK
    assert "Divides without guarding zero" in result.stdout
    assert "Off-by-one in the slice" in result.stdout


@pytest.mark.e2e
def test_a_clean_file_exits_zero_and_says_so() -> None:
    result = runner.invoke(_app(_analyzing()), ["app.py"])

    assert result.exit_code == ExitCode.OK
    assert "no findings" in result.stdout


@pytest.mark.e2e
def test_the_model_and_token_cost_are_reported() -> None:
    """The user paid for the call; they get to see for what."""
    result = runner.invoke(_app(_analyzing(*FINDINGS)), ["app.py"])

    assert "fake-model" in result.stdout
    assert "120" in result.stdout
    assert "45" in result.stdout


@pytest.mark.e2e
def test_findings_are_ordered_most_serious_first() -> None:
    result = runner.invoke(_app(_analyzing(*FINDINGS)), ["app.py"])

    high = result.stdout.index("Divides without guarding zero")
    medium = result.stdout.index("Off-by-one in the slice")
    assert high < medium


@pytest.mark.e2e
def test_plain_output_has_no_box_drawing() -> None:
    """A pipe, a log, and a CI transcript all want text, not borders."""
    result = runner.invoke(_app(_analyzing(*FINDINGS)), ["app.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert "Divides without guarding zero" in result.stdout
    assert "line 2" in result.stdout
    assert not set("┏┓┗┛━┃│─") & set(result.stdout)


# --- exit code 1: ran, but produced no result ------------------------------


@pytest.mark.e2e
def test_an_unusable_model_reply_exits_one() -> None:
    analyze = AnalyzeSourceFile(
        FakeSourceReader(source=SOURCE),
        FakeProvider(
            response=CompletionResponse(
                text="I am afraid I cannot do that.",
                model="fake-model",
                usage=TokenUsage(input_tokens=1, output_tokens=1),
            )
        ),
    )

    result = runner.invoke(_app(analyze), ["app.py"])

    assert result.exit_code == ExitCode.FAILED


# --- exit code 2: unusable input -------------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize(
    "error",
    [
        SourceNotFoundError("No such file: missing.py"),
        SourceTooLargeError("app.py is 900,000 bytes, over the limit."),
        PathOutsideWorkspaceError("../secret.py resolves outside the workspace."),
    ],
    ids=["missing", "too-large", "outside-workspace"],
)
def test_unusable_input_exits_two(error: Exception) -> None:
    result = runner.invoke(_app(_failing(error)), ["whatever.py"])

    assert result.exit_code == ExitCode.BAD_INPUT


# --- exit code 3: not configured -------------------------------------------


@pytest.mark.e2e
def test_a_missing_api_key_exits_three() -> None:
    result = runner.invoke(
        _app(_failing(ConfigurationError("No API key configured. Set FORGE_API_KEY."))),
        ["app.py"],
    )

    assert result.exit_code == ExitCode.NOT_CONFIGURED


# --- exit code 4: the provider failed --------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize(
    "error",
    [ProviderTimeoutError("timed out"), ProviderRateLimitError("slow down")],
    ids=["timeout", "rate-limit"],
)
def test_a_provider_failure_exits_four(error: Exception) -> None:
    result = runner.invoke(_app(_failing(error)), ["app.py"])

    assert result.exit_code == ExitCode.PROVIDER_FAILED


# --- messages ---------------------------------------------------------------


@pytest.mark.e2e
def test_an_error_message_says_what_to_do_next() -> None:
    """NFR-3.1. A message that only states the problem wastes the reader."""
    result = runner.invoke(
        _app(
            _failing(
                ConfigurationError(
                    "No API key configured. Set FORGE_API_KEY in your environment."
                )
            )
        ),
        ["app.py"],
    )

    assert "FORGE_API_KEY" in result.output


@pytest.mark.e2e
def test_errors_do_not_print_a_traceback() -> None:
    """A traceback tells a user nothing they can act on."""
    result = runner.invoke(
        _app(_failing(SourceNotFoundError("No such file"))), ["x.py"]
    )

    assert "Traceback" not in result.output
    assert "forge:" in result.output


# --- the command surface ----------------------------------------------------


@pytest.mark.e2e
def test_the_path_argument_is_required() -> None:
    result = runner.invoke(_app(_analyzing()), [])

    assert result.exit_code != ExitCode.OK


@pytest.mark.e2e
def test_help_documents_the_exit_codes() -> None:
    """The contract is only usable if a user can find it."""
    result = runner.invoke(_app(_analyzing()), ["--help"])

    assert "0" in result.stdout
    assert "provider failed" in result.stdout.lower()


@pytest.mark.e2e
def test_help_says_findings_do_not_change_the_exit_code() -> None:
    """Users arriving from linters expect the opposite. Say so plainly."""
    result = runner.invoke(_app(_analyzing()), ["--help"])

    assert "exit code" in result.stdout.lower()
