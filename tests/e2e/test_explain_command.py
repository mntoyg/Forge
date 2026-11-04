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


@pytest.mark.e2e
def test_observed_repetition_and_name_only_symbols_render_as_distinct_roles() -> None:
    source = SourceFile(
        Path("explain.py"),
        "class ExplainSource:\n"
        "    def __call__(self, path):\n"
        "        source = self._reader.read(path)\n"
        "        response = self._provider.complete(source)\n"
        "        return parse_explanation(response, source)\n",
    )
    provider = FakeProvider(
        response=CompletionResponse(
            text=json.dumps(
                {
                    "purpose": [
                        {
                            "claim": "Explains one selected source file.",
                            "confidence": "certain",
                            "evidence": [{"start_line": 1, "end_line": 5}],
                        }
                    ],
                    "flow": [
                        {
                            "claim": "Explains one selected source file.",
                            "confidence": "certain",
                            "evidence": [{"start_line": 1, "end_line": 5}],
                        },
                        {
                            "claim": "Reads the source, requests one provider response, then validates it.",
                            "confidence": "certain",
                            "evidence": [{"start_line": 3, "end_line": 5}],
                        },
                    ],
                    "symbols": [
                        {
                            "claim": "ExplainSource class",
                            "confidence": "certain",
                            "evidence": [{"start_line": 1, "end_line": 1}],
                        },
                        {
                            "claim": "__call__ method",
                            "confidence": "certain",
                            "evidence": [{"start_line": 2, "end_line": 2}],
                        },
                        {
                            "claim": "Coordinates source reading and the provider request.",
                            "confidence": "certain",
                            "evidence": [{"start_line": 2, "end_line": 4}],
                        },
                        {
                            "claim": "Validates the provider response against source lines.",
                            "confidence": "certain",
                            "evidence": [{"start_line": 5, "end_line": 5}],
                        },
                    ],
                    "limitations": [],
                    "context_insufficient": False,
                }
            ),
            model="fake-model",
            usage=TokenUsage(input_tokens=45, output_tokens=30),
        )
    )
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["explain.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert result.stdout.count("Explains one selected source file.") == 1
    assert "No distinct claims beyond earlier sections." not in result.stdout
    assert (
        "Reads the source, requests one provider response, then validates it."
        in result.stdout
    )
    assert "Coordinates source reading and the provider request." in result.stdout
    assert "Validates the provider response against source lines." in result.stdout
    assert "ExplainSource class" not in result.stdout
    assert "__call__ method" not in result.stdout
    assert "[certain]" not in result.stdout
    assert provider.call_count == 1


@pytest.mark.e2e
def test_flow_and_symbol_roles_cite_usage_sites_from_the_submitted_snapshot() -> None:
    lines = (
        '"""Explain one selected source file."""',
        "from pathlib import Path",
        "",
        "from forge.application.explain_parsing import parse_explanation",
        "from forge.application.explain_prompt import build_explain_request",
        "from forge.domain.ai import AIProvider",
        "from forge.domain.explanation import ExplanationResult",
        "from forge.domain.source import SourceReader",
        "",
        "class ExplainSource:",
        "    def __init__(self, reader: SourceReader, provider: AIProvider) -> None:",
        "        self._reader = reader",
        "        self._provider = provider",
        "",
        "    def __call__(self, path: Path) -> ExplanationResult:",
        "        source = self._reader.read(path)",
        "        request = build_explain_request(source)",
        "        response = self._provider.complete(request)",
        "        return parse_explanation(response.text, source)",
    )
    source = SourceFile(Path("explain.py"), "\n".join(lines))
    provider = FakeProvider(
        response=CompletionResponse(
            text=json.dumps(
                {
                    "purpose": [
                        {
                            "claim": "Coordinates one evidence-backed explanation for the selected file.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 10, "end_line": 19}],
                        }
                    ],
                    "flow": [
                        {
                            "claim": "Reads the selected source through the configured reader.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 16, "end_line": 16}],
                        },
                        {
                            "claim": "Builds a request from that source snapshot.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 17, "end_line": 17}],
                        },
                        {
                            "claim": "Makes one provider call with the request.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 18, "end_line": 18}],
                        },
                        {
                            "claim": "Parses the response against the same source and returns the result.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 19, "end_line": 19}],
                        },
                    ],
                    "symbols": [
                        {
                            "claim": "The reader supplies the selected file snapshot.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 16, "end_line": 16}],
                        },
                        {
                            "claim": "The request builder packages the snapshot for the provider.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 17, "end_line": 17}],
                        },
                        {
                            "claim": "The provider port performs the single external completion call.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 18, "end_line": 18}],
                        },
                        {
                            "claim": "The parser validates the response with the original snapshot.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 19, "end_line": 19}],
                        },
                        {
                            "claim": "The return annotation names the validated result type.",
                            "confidence": "likely",
                            "evidence": [{"start_line": 15, "end_line": 15}],
                        },
                    ],
                    "limitations": [],
                    "context_insufficient": False,
                }
            ),
            model="fake-model",
            usage=TokenUsage(input_tokens=75, output_tokens=65),
        )
    )
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["explain.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert provider.call_count == 1
    submitted = provider.requests[0].messages[1].content
    for line_number, line in enumerate(lines, start=1):
        assert f"{line_number:>4} | {line}" in submitted
    flow = result.stdout.split("Main flow:", 1)[1].split("Important symbols:", 1)[0]
    symbols = result.stdout.split("Important symbols:", 1)[1].split("Limitations:", 1)[
        0
    ]
    assert "Reads the selected source" in flow
    assert "Builds a request" in flow
    assert "Makes one provider call" in flow
    assert "Parses the response" in flow
    assert "__init__" not in flow
    assert "_reader = reader" not in flow
    assert "The reader supplies" in symbols
    assert "The request builder packages" in symbols
    assert "The provider port performs" in symbols
    assert "The parser validates" in symbols
    assert "The return annotation names" in symbols
    for claim, line_number in (
        ("The reader supplies the selected file snapshot.", 16),
        ("The request builder packages the snapshot for the provider.", 17),
        ("The provider port performs the single external completion call.", 18),
        ("The parser validates the response with the original snapshot.", 19),
        ("The return annotation names the validated result type.", 15),
    ):
        assert f"{claim}\n    Evidence: lines {line_number}-{line_number}" in symbols
    for line_number in range(15, 20):
        assert f"Evidence: lines {line_number}-{line_number}" in result.stdout
        assert f"{line_number:>4} | {lines[line_number - 1]}" in result.stdout
    for import_line in range(4, 9):
        assert f"Evidence: lines {import_line}-{import_line}" not in symbols
