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


def _anchor(
    kind: str, target: str, start: int, end: int | None = None
) -> dict[str, object]:
    return {
        "kind": kind,
        "target": target,
        "start_line": start,
        "end_line": start if end is None else end,
    }


def _provider(error: Exception | None = None) -> FakeProvider:
    response = CompletionResponse(
        text=json.dumps(
            {
                "purpose": [
                    {
                        "claim": "Sets a value.",
                        "confidence": "likely",
                        "evidence": [_anchor("operation", "value = 1", 1)],
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
    assert "Evidence: operation target `value = 1`, lines 1-1" in result.stdout
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
def test_non_python_source_keeps_single_call_but_marks_evidence_incomplete() -> None:
    provider = _provider()
    source = SourceFile(Path("app.ts"), "value = 1\n")
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["app.ts", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert provider.call_count == 1
    assert "Sets a value." not in result.stdout
    assert "Incomplete:" in result.stdout
    assert (
        "Evidence validation supports Python .py and .pyi files only" in result.stdout
    )
    assert "   1 | value = 1" in provider.requests[0].messages[1].content


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
                            "evidence": [_anchor("operation", "value = 1", 99)],
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
                            "evidence": [_anchor("operation", "source", 1, 5)],
                        }
                    ],
                    "flow": [
                        {
                            "claim": "Explains one selected source file.",
                            "confidence": "certain",
                            "evidence": [_anchor("operation", "source", 1, 5)],
                        },
                        {
                            "claim": "Reads the source, requests one provider response, then validates it.",
                            "confidence": "certain",
                            "evidence": [
                                _anchor("call", "self._reader.read", 3),
                                _anchor("call", "self._provider.complete", 4),
                            ],
                        },
                    ],
                    "symbols": [
                        {
                            "symbol": "ExplainSource",
                            "claim": "ExplainSource class",
                            "confidence": "certain",
                            "evidence": [_anchor("call", "self._reader.read", 3)],
                        },
                        {
                            "symbol": "__call__",
                            "claim": "__call__ method",
                            "confidence": "certain",
                            "evidence": [_anchor("call", "self._reader.read", 3)],
                        },
                        {
                            "symbol": "ExplainSource",
                            "claim": "Coordinates source reading and the provider request.",
                            "confidence": "certain",
                            "evidence": [
                                _anchor("call", "self._provider.complete", 4),
                                _anchor("call", "parse_explanation", 5),
                            ],
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
    assert "ExplainSource class" not in result.stdout
    assert "__call__ method" not in result.stdout
    assert (
        "ExplainSource: Coordinates source reading and the provider request."
        in result.stdout
    )
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
                            "evidence": [
                                _anchor("call", "self._provider.complete", 18)
                            ],
                        }
                    ],
                    "flow": [
                        {
                            "claim": "Reads the selected source through the configured reader.",
                            "confidence": "likely",
                            "evidence": [_anchor("call", "self._reader.read", 16)],
                        },
                        {
                            "claim": "Builds a request from that source snapshot.",
                            "confidence": "likely",
                            "evidence": [_anchor("call", "build_explain_request", 17)],
                        },
                        {
                            "claim": "Makes one provider call with the request.",
                            "confidence": "likely",
                            "evidence": [
                                _anchor("call", "self._provider.complete", 18)
                            ],
                        },
                        {
                            "claim": "Parses the response against the same source and returns the result.",
                            "confidence": "likely",
                            "evidence": [_anchor("call", "parse_explanation", 19)],
                        },
                    ],
                    "symbols": [
                        {
                            "symbol": "ExplainSource",
                            "claim": "Coordinates the selected-file read, provider call, and response parsing against one source snapshot.",
                            "confidence": "likely",
                            "evidence": [
                                _anchor("call", "self._reader.read", 16),
                                _anchor("call", "self._provider.complete", 18),
                                _anchor("call", "parse_explanation", 19),
                            ],
                        }
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
    assert (
        "ExplainSource: Coordinates the selected-file read, provider call, and "
        "response parsing against one source snapshot."
    ) in symbols
    for line_number in (16, 18, 19):
        assert f"lines {line_number}-{line_number}" in symbols
    for line_number in (16, 18, 19):
        assert f"lines {line_number}-{line_number}" in result.stdout
        assert f"{line_number:>4} | {lines[line_number - 1]}" in result.stdout
    for import_line in range(4, 9):
        assert f"lines {import_line}-{import_line}" not in symbols


@pytest.mark.e2e
def test_purpose_and_return_type_cite_their_actual_use_sites() -> None:
    lines = (
        '"""Explain a selected source file through an AI provider."""',
        '"""The provider-backed explanation uses the submitted file snapshot."""',
        "",
        "from pathlib import Path",
        "",
        "from forge.application.explain_parsing import parse_explanation",
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
        "        response = self._provider.complete(source)",
        "        return parse_explanation(",
        "            response.text,",
        "            source,",
        "        )",
    )
    source = SourceFile(Path("explain.py"), "\n".join(lines))
    provider = FakeProvider(
        response=CompletionResponse(
            text=json.dumps(
                {
                    "purpose": [
                        {
                            "claim": "Uses the configured provider to obtain an explanation of the selected source.",
                            "confidence": "likely",
                            "evidence": [
                                _anchor("call", "self._provider.complete", 18)
                            ],
                        }
                    ],
                    "flow": [],
                    "symbols": [
                        {
                            "symbol": "ExplainSource",
                            "claim": "Returns the declared result type after parsing the provider response against the submitted source.",
                            "confidence": "likely",
                            "evidence": [
                                _anchor("return_type", "ExplanationResult", 16),
                                _anchor("return_value", "parse_explanation", 19, 22),
                            ],
                        }
                    ],
                    "limitations": [],
                    "context_insufficient": False,
                }
            ),
            model="fake-model",
            usage=TokenUsage(input_tokens=40, output_tokens=20),
        )
    )
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["explain.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert provider.call_count == 1
    submitted = provider.requests[0].messages[1].content
    for line_number, line in enumerate(lines, start=1):
        assert f"{line_number:>4} | {line}" in submitted
    purpose = result.stdout.split("Purpose:", 1)[1].split("Main flow:", 1)[0]
    symbols = result.stdout.split("Important symbols:", 1)[1].split("Limitations:", 1)[
        0
    ]
    assert "Evidence: call target `self._provider.complete`, lines 18-18" in purpose
    assert f"18 | {lines[17]}" in purpose
    assert "Evidence: return_type target `ExplanationResult`, lines 16-16" in symbols
    assert "ExplainSource: Returns the declared result type" in symbols
    assert f"16 | {lines[15]}" in symbols
    assert "Evidence: return_value target `parse_explanation`, lines 19-22" in symbols
    for line_number in range(19, 23):
        assert f"{line_number:>4} | {lines[line_number - 1]}" in symbols
    assert "lines 8-8" not in symbols
    assert "lines 22-22" not in symbols


@pytest.mark.e2e
def test_mismatched_anchor_kinds_and_declaration_sites_are_omitted() -> None:
    lines = (
        '"""Explain the provider-backed result."""',
        "from forge.domain.explanation import ExplanationResult",
        "",
        "class ExplainSource:",
        "    def __init__(self, reader, provider):",
        "        self._reader = reader",
        "        self._provider = provider",
        "",
        "    def __call__(self, path):",
        "        source = self._reader.read(path)",
        "        response = self._provider.complete(source)",
        "        return source",
    )
    source = SourceFile(Path("explain.py"), "\n".join(lines))
    claims = {
        "purpose": [
            {
                "claim": "Uses the configured provider for this explanation.",
                "confidence": "likely",
                "evidence": [_anchor("call", "self._provider.complete", 1)],
            }
        ],
        "flow": [],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": "The reader supplies the selected source.",
                "confidence": "likely",
                "evidence": [_anchor("access", "self._reader", 6)],
            },
            {
                "symbol": "ExplainSource",
                "claim": "The provider makes a completion request.",
                "confidence": "likely",
                "evidence": [_anchor("call", "self._provider.complete", 7)],
            },
            {
                "symbol": "ExplainSource",
                "claim": "ExplanationResult is the returned result type.",
                "confidence": "likely",
                "evidence": [_anchor("return_type", "ExplanationResult", 2)],
            },
            {
                "symbol": "ExplainSource",
                "claim": "The return expression produces the explanation result.",
                "confidence": "likely",
                "evidence": [_anchor("return_value", "parse_explanation", 12)],
            },
        ],
        "limitations": [],
        "context_insufficient": False,
    }
    provider = FakeProvider(
        response=CompletionResponse(
            text=json.dumps(claims),
            model="fake-model",
            usage=TokenUsage(input_tokens=45, output_tokens=12),
        )
    )
    app = _app(lambda: ExplainSource(FakeSourceReader(source=source), provider))

    result = runner.invoke(app, ["explain.py", "--plain"])

    assert result.exit_code == ExitCode.OK
    assert provider.call_count == 1
    assert "Uses the configured provider" not in result.stdout
    assert "The reader supplies" not in result.stdout
    assert "The provider makes" not in result.stdout
    assert "ExplanationResult is" not in result.stdout
    assert "return expression produces" not in result.stdout
    assert "Incomplete:" in result.stdout
