"""The `forge review` CLI flow, exercised with a deterministic provider fake."""

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from forge.application.review import ReviewChanges
from forge.cli import review as review_cli
from forge.cli.exit_codes import ExitCode
from forge.domain.ai import CompletionResponse, TokenUsage
from forge.domain.review import (
    ChangeKind,
    ChangeSet,
    ReviewFile,
)
from forge.main import app as forge_app
from tests.support.fakes import FakeProvider

runner = CliRunner()


class _TerminalInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _TerminalOutput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _ChangeSet:
    """A single current file with one changed line for CLI scenarios."""

    def read(self, paths: tuple[Path, ...] = ()) -> ChangeSet:
        return ChangeSet(
            root=Path.cwd(),
            files=(
                ReviewFile(
                    path=Path("src/app.py"),
                    content="value = 1\n",
                    changed_lines=frozenset({1}),
                    kind=ChangeKind.MODIFIED,
                ),
            ),
            omissions=(),
        )


def _cli_app(provider: FakeProvider, created: list[ReviewChanges]) -> typer.Typer:
    app = typer.Typer()

    def factory() -> ReviewChanges:
        use_case = ReviewChanges(_ChangeSet(), provider, model="configured-model")
        created.append(use_case)
        return use_case

    review_cli.register(app, factory)
    return app


def _provider() -> FakeProvider:
    return FakeProvider(
        response=CompletionResponse(
            text=json.dumps(
                {
                    "findings": [
                        {
                            "path": "src/app.py",
                            "line": 1,
                            "summary": "Suspicious value",
                            "detail": "The value is likely incorrect.",
                            "severity": "medium",
                            "confidence": "likely",
                        }
                    ]
                }
            ),
            model="fake-model",
            usage=TokenUsage(input_tokens=120, output_tokens=35),
        )
    )


@pytest.mark.e2e
def test_help_does_not_construct_the_provider_use_case() -> None:
    provider = _provider()
    created: list[ReviewChanges] = []

    result = runner.invoke(_cli_app(provider, created), ["--help"])

    assert result.exit_code == 0
    assert "review" in result.stdout
    assert not created
    assert provider.call_count == 0


@pytest.mark.e2e
def test_registered_review_help_works_without_an_api_key() -> None:
    result = runner.invoke(forge_app, ["review", "--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "configured provider and API key" in review_cli.HELP


@pytest.mark.e2e
def test_non_interactive_review_prints_plan_without_calling_provider() -> None:
    provider = _provider()
    created: list[ReviewChanges] = []

    result = runner.invoke(_cli_app(provider, created), ["src"])

    assert result.exit_code == ExitCode.FAILED
    assert "src/app.py" in result.stdout
    assert "configured-model" in result.stdout
    assert "at most 1" in result.stdout
    assert "No review was sent" in result.stderr
    assert provider.call_count == 0
    assert created[0] is not None


@pytest.mark.e2e
def test_declining_confirmation_makes_no_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider()
    created: list[ReviewChanges] = []
    monkeypatch.setattr(
        review_cli,
        "sys",
        SimpleNamespace(
            stdin=_TerminalInput(), stdout=_TerminalOutput(), stderr=io.StringIO()
        ),
    )
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: False)

    result = runner.invoke(_cli_app(provider, created), [])

    assert result.exit_code == ExitCode.OK
    assert "Review plan" in result.stdout
    assert provider.call_count == 0


@pytest.mark.e2e
def test_terminal_input_without_visible_stdout_does_not_ask_or_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider()
    created: list[ReviewChanges] = []
    stderr = io.StringIO()
    monkeypatch.setattr(
        review_cli,
        "sys",
        SimpleNamespace(stdin=_TerminalInput(), stdout=io.StringIO(), stderr=stderr),
    )
    monkeypatch.setattr(
        typer,
        "confirm",
        lambda *args, **kwargs: pytest.fail("hidden prompt must not be confirmed"),
    )

    result = runner.invoke(_cli_app(provider, created), [])

    assert result.exit_code == ExitCode.FAILED
    assert "interactive terminal" in stderr.getvalue()
    assert provider.call_count == 0


@pytest.mark.e2e
def test_confirmation_makes_one_call_and_shows_validated_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider()
    created: list[ReviewChanges] = []

    def confirm(*args: object, **kwargs: object) -> bool:
        print("confirmation prompt reached")
        return True

    monkeypatch.setattr(
        review_cli,
        "sys",
        SimpleNamespace(
            stdin=_TerminalInput(), stdout=_TerminalOutput(), stderr=io.StringIO()
        ),
    )
    monkeypatch.setattr(typer, "confirm", confirm)

    result = runner.invoke(_cli_app(provider, created), [])

    assert result.exit_code == ExitCode.OK
    assert provider.call_count == 1
    assert result.stdout.index("Omitted paths:") < result.stdout.index(
        "confirmation prompt reached"
    )
    assert "src/app.py:line 1" in result.stdout
    assert "Evidence: value = 1" in result.stdout
    assert "120 in, 35 out" in result.stdout
