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
from datetime import date
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
    NoChangesError,
    NotARepositoryError,
    PathOutsideWorkspaceError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    SourceNotFoundError,
    SourceTooLargeError,
)
from forge.domain.source import ChangeRecord, FileHistory, SourceFile
from tests.support.fakes import (
    FakeProvider,
    FakeRepositoryInspector,
    FakeSourceReader,
)

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


def _app(analyze: Callable[..., object]) -> typer.Typer:
    """Build a one-command app around ``analyze``."""
    app = typer.Typer()
    debug_cli.register(app, analyze)  # type: ignore[arg-type]
    return app


def _analyzing(*findings: object) -> Callable[..., object]:
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


def _failing(error: Exception) -> Callable[..., object]:
    def analyze(path: Path, *, changes_only: bool = False) -> object:
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


@pytest.mark.e2e
@pytest.mark.parametrize(
    "error",
    [
        NotARepositoryError("not inside a git repository"),
        NoChangesError("app.py has no uncommitted changes"),
    ],
    ids=["not-a-repo", "no-changes"],
)
def test_a_repository_problem_exits_two(error: Exception) -> None:
    """A request that cannot be satisfied is unusable input, like a bad path.

    ADR-0006 warns that a wide table invites codes nobody handles, so these
    share code 2 rather than taking one of their own.
    """
    result = runner.invoke(_app(_failing(error)), ["app.py", "--diff"])

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


# --- the --diff flag ---------------------------------------------------------


@pytest.mark.e2e
def test_the_diff_flag_asks_for_a_change_review() -> None:
    seen: dict[str, object] = {}

    def analyze(path: Path, *, changes_only: bool = False) -> object:
        seen["changes_only"] = changes_only
        return _analyzing(*FINDINGS)(path)

    runner.invoke(_app(analyze), ["app.py", "--diff"])

    assert seen["changes_only"] is True


@pytest.mark.e2e
def test_without_the_flag_no_change_review_is_asked_for() -> None:
    """Someone outside version control must keep the rest of the command."""
    seen: dict[str, object] = {}

    def analyze(path: Path, *, changes_only: bool = False) -> object:
        seen["changes_only"] = changes_only
        return _analyzing(*FINDINGS)(path)

    runner.invoke(_app(analyze), ["app.py"])

    assert seen["changes_only"] is False


@pytest.mark.e2e
def test_help_says_diff_narrows_the_answer_not_the_bill() -> None:
    """ADR-0008: a user expecting a cheaper run would be misled by us.

    Asserted against the help text itself rather than against rendered output.
    Rich wraps to the terminal width, so a rendered assertion passes or fails
    depending on the width of whatever ran it - which is how this test first
    passed on Windows and failed on CI.
    """
    help_text = debug_cli.HELP

    assert "--diff" in help_text
    assert "narrows the answer rather than the bill" in help_text


# --- the command surface ----------------------------------------------------


@pytest.mark.e2e
def test_the_path_argument_is_required() -> None:
    result = runner.invoke(_app(_analyzing()), [])

    assert result.exit_code != ExitCode.OK


@pytest.mark.e2e
def test_help_documents_the_exit_codes() -> None:
    """The contract is only usable if a user can find it."""
    help_text = debug_cli.HELP.lower()

    for code, meaning in [
        ("0", "analysis completed"),
        ("1", "could not produce a result"),
        ("2", "unusable input"),
        ("3", "not configured"),
        ("4", "provider failed"),
    ]:
        assert code in help_text
        assert meaning in help_text


@pytest.mark.e2e
def test_help_says_findings_do_not_change_the_exit_code() -> None:
    """Users arriving from linters expect the opposite. Say so plainly."""
    assert "Findings do not change the exit code" in debug_cli.HELP


@pytest.mark.e2e
def test_the_help_text_actually_reaches_the_user() -> None:
    """The assertions above read a constant; this proves Typer renders it.

    Without it, the help could stop being attached to the command and every
    other help test would still pass.
    """
    result = runner.invoke(_app(_analyzing()), ["--help"])

    assert result.exit_code == 0
    assert "Analyse a source file" in result.stdout


# --- history reaches the user -----------------------------------------------


HISTORY = FileHistory(
    recent_commits=4,
    window_days=90,
    records=(
        ChangeRecord(
            line=2, commit="a1b2c3d", author="A U Thor", changed_on=date(2026, 1, 15)
        ),
    ),
)


def _analyzing_in_a_repository(*findings: object) -> Callable[..., object]:
    return AnalyzeSourceFile(
        FakeSourceReader(source=SOURCE),
        FakeProvider(
            response=CompletionResponse(
                text=json.dumps({"findings": list(findings)}),
                model="fake-model",
                usage=TokenUsage(input_tokens=120, output_tokens=45),
            )
        ),
        FakeRepositoryInspector(history=HISTORY),
    )


@pytest.mark.e2e
def test_a_finding_arrives_with_what_git_knows_about_its_line() -> None:
    """Asserted on plain output: Rich wraps to the terminal running the test."""
    result = runner.invoke(
        _app(_analyzing_in_a_repository(FINDINGS[0])), ["app.py", "--plain"]
    )

    assert result.exit_code == ExitCode.OK
    assert "a1b2c3d" in result.stdout
    assert "2026-01-15" in result.stdout


@pytest.mark.e2e
def test_a_piped_run_carries_no_escape_codes() -> None:
    """The spinner must never reach a log file, a pipe, or a CI transcript."""
    result = runner.invoke(_app(_analyzing(*FINDINGS)), ["app.py", "--plain"])

    assert "[" not in result.stdout


@pytest.mark.e2e
def test_outside_a_repository_the_findings_still_arrive() -> None:
    """History is context around the answer, never a condition for getting one."""
    result = runner.invoke(_app(_analyzing(FINDINGS[0])), ["app.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert "Divides without guarding zero" in result.stdout
    assert "history:" not in result.stdout
