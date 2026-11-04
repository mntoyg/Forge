import json
from pathlib import Path

import pytest

from forge.application.explain import ExplainSource
from forge.application.explain_prompt import build_explain_request
from forge.domain.ai import CompletionResponse, Role, TokenUsage
from forge.domain.errors import ProviderTimeoutError, SourceNotFoundError
from forge.domain.source import SourceFile
from tests.support.fakes import FakeProvider, FakeSourceReader


def _response(payload: dict[str, object]) -> CompletionResponse:
    return CompletionResponse(
        text=json.dumps(payload),
        model="fake-model",
        usage=TokenUsage(input_tokens=12, output_tokens=8),
    )


def _valid_payload() -> dict[str, object]:
    return {
        "purpose": [
            {
                "claim": "Calculates a total.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "operation",
                        "target": "value = 1",
                        "start_line": 1,
                        "end_line": 2,
                    }
                ],
            }
        ],
        "flow": [],
        "symbols": [],
        "limitations": [],
        "context_insufficient": False,
    }


def test_prompt_includes_only_the_complete_numbered_source_snapshot() -> None:
    source = SourceFile(Path("app.py"), "value = 1\nprint(value)\n")

    request = build_explain_request(source)
    prompt = " ".join(request.messages[0].content.split())

    assert len(request.messages) == 2
    assert request.messages[0].role is Role.SYSTEM
    assert "untrusted DATA" in request.messages[0].content
    assert "validated only for Python source files" in request.messages[0].content
    assert "exact target copied from the source" in request.messages[0].content
    assert '"kind":"call"' in request.messages[0].content
    assert "not its step-by-step" in request.messages[0].content
    assert "distinct responsibility" in request.messages[0].content
    assert "Each symbol entry must describe exactly one" in prompt
    assert "Emit separate entries for the same symbol" in prompt
    assert "A call anchor must identify an actual call expression" in prompt
    assert "never a function or method declaration" in prompt
    assert "Each symbols entry must include `symbol`" in request.messages[0].content
    assert "Python's AST" in request.messages[0].content
    assert "Do not present constructor or initialization" in request.messages[0].content
    assert "entry point that handles the" in request.messages[0].content
    assert "import line only establishes" in request.messages[0].content
    assert "Prefer call, construction, access, or" in request.messages[0].content
    assert "actual provider call as evidence" in request.messages[0].content
    assert "return annotation and/or the code that" in request.messages[0].content
    assert "closing delimiter alone does not" in request.messages[0].content
    assert (
        '"certain" only for a literal fact directly established'
        in request.messages[0].content
    )
    assert request.messages[1].content.endswith("   1 | value = 1\n   2 | print(value)")
    assert request.temperature == 0.0


def test_use_case_reads_once_and_makes_one_provider_call() -> None:
    source = SourceFile(Path("app.py"), "value = 1\nprint(value)\n")
    reader = FakeSourceReader(source=source)
    provider = FakeProvider(response=_response(_valid_payload()))

    result = ExplainSource(reader, provider)(Path("app.py"))

    assert reader.paths == [Path("app.py")]
    assert provider.call_count == 1
    assert result.source is source


def test_unreadable_source_fails_before_provider_call() -> None:
    provider = FakeProvider(response=_response(_valid_payload()))

    with pytest.raises(SourceNotFoundError):
        ExplainSource(FakeSourceReader(error=SourceNotFoundError("missing")), provider)(
            Path("missing.py")
        )

    assert provider.call_count == 0


def test_provider_failure_is_not_retried() -> None:
    provider = FakeProvider(error=ProviderTimeoutError("timed out"))

    with pytest.raises(ProviderTimeoutError):
        ExplainSource(FakeSourceReader(), provider)(Path("app.py"))

    assert provider.call_count == 1
