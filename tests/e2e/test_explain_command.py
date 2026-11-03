import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from forge.application.explain import ExplainSource
from forge.cli import explain as explain_cli
from forge.cli.exit_codes import ExitCode
from forge.domain.ai import CompletionResponse, TokenUsage
from forge.domain.errors import (
    ConfigurationError,
    ProviderTimeoutError,
    SourceNotFoundError,
)
from forge.domain.source import SourceFile
from forge.infrastructure.source import FilesystemSourceReader
from forge.main import app as forge_app
from tests.support.fakes import FakeProvider, FakeSourceReader

runner = CliRunner()


def _provider(error: Exception | None = None) -> FakeProvider:
    response = CompletionResponse(
        text=json.dumps(
            {
                "purpose": [
                    {
                        "claim": "Sets a value.",
                        "confidence": "likely",
                        "evidence": [{"start_line": 1, "end_line": 1}],
                    }
                ],
                "flow": [],
                "symbols": [],
                "limitations": [],
                "context_insufficient": False,
            }
        ),
        model="fake-model",
        usage=TokenUsage(input_tokens=15, output_tokens=7),
    )
    return FakeProvider(response=None if error else response, error=error)


def _app(factory: object) -> typer.Typer:
    app = typer.Typer()
    explain_cli.register(app, factory)  # type: ignore[arg-type]
    return app


@pytest.mark.e2e
def test_registered_help_discloses_provider_use_without_loading_config() -> None:
    result = runner.invoke(forge_app, ["explain", "--help"])

    assert result.exit_code == ExitCode.OK
    assert "selected file is sent to the provider" in result.stdout
    assert "Usage:" in result.stdout


@pytest.mark.e2e
def test_plain_cli_output_uses_one_fake_call_and_writes_no_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "app.py"
    original = b"value = 1\n"
    path.write_bytes(original)
    monkeypatch.chdir(tmp_path)
    provider = _provider()
    app = _app(lambda: ExplainSource(FilesystemSourceReader(tmp_path), provider))

    result = runner.invoke(app, ["app.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert "Sets a value." in result.stdout
    assert "Evidence: lines 1-1" in result.stdout
    assert "15 in, 7 out" in result.stdout
    assert "selected file is sent" not in result.stderr
    assert provider.call_count == 1
    assert path.read_bytes() == original


@pytest.mark.e2e
def test_missing_configuration_is_exit_three_and_does_not_call_provider() -> None:
    provider = _provider()

    def missing_configuration() -> ExplainSource:
        raise ConfigurationError("Set FORGE_API_KEY.")

    result = runner.invoke(_app(missing_configuration), ["app.py"])

    assert result.exit_code == ExitCode.NOT_CONFIGURED
    assert "FORGE_API_KEY" in result.stderr
    assert provider.call_count == 0


@pytest.mark.e2e
def test_provider_failure_is_exit_four_after_one_call() -> None:
    provider = _provider(ProviderTimeoutError("timed out"))
    source = SourceFile(Path("app.py"), "value = 1\n")
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["app.py", "--plain"])

    assert result.exit_code == ExitCode.PROVIDER_FAILED
    assert "timed out" in result.stderr
    assert provider.call_count == 1


@pytest.mark.e2e
def test_missing_source_is_exit_two_without_provider_call() -> None:
    provider = _provider()
    app = _app(
        lambda: ExplainSource(
            FakeSourceReader(error=SourceNotFoundError("No such file: app.py")),
            provider,
        )
    )

    result = runner.invoke(app, ["app.py", "--plain"])

    assert result.exit_code == ExitCode.BAD_INPUT
    assert "No such file" in result.stderr
    assert provider.call_count == 0


@pytest.mark.e2e
def test_unusable_provider_response_is_exit_one_after_one_call() -> None:
    provider = FakeProvider(
        response=CompletionResponse(
            text="not JSON", model="fake-model", usage=TokenUsage(1, 1)
        )
    )
    source = SourceFile(Path("app.py"), "value = 1\n")
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["app.py", "--plain"])

    assert result.exit_code == ExitCode.FAILED
    assert "not valid JSON" in result.stderr
    assert provider.call_count == 1


@pytest.mark.e2e
def test_unsupported_claim_is_omitted_and_result_is_visibly_incomplete() -> None:
    provider = FakeProvider(
        response=CompletionResponse(
            text=json.dumps(
                {
                    "purpose": [
                        {
                            "claim": "Unsupported claim.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 99, "end_line": 99}],
                        }
                    ],
                    "flow": [],
                    "symbols": [],
                    "limitations": [],
                    "context_insufficient": False,
                }
            ),
            model="fake-model",
            usage=TokenUsage(input_tokens=15, output_tokens=7),
        )
    )
    source = SourceFile(Path("app.py"), "value = 1\n")
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["app.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert "Unsupported claim." not in result.stdout
    assert "Incomplete:" in result.stdout
    assert provider.call_count == 1
