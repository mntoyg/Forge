"""The analyse use case, driven entirely through fakes.

No filesystem, no network, no key. That this is possible at all is the payoff
of the two ports; that it runs in microseconds is why the failure branches are
worth testing exhaustively here rather than end to end.
"""

import json
from pathlib import Path

import pytest

from forge.application.analyze import AnalyzeSourceFile
from forge.domain.ai import CompletionResponse, Role, TokenUsage
from forge.domain.errors import (
    ProviderRateLimitError,
    ProviderResponseError,
    SourceNotFoundError,
    SourceTooLargeError,
)
from forge.domain.source import Severity, SourceFile
from tests.support.fakes import FakeProvider, FakeSourceReader

SOURCE = SourceFile(path=Path("app.py"), content="a = 1\nb = 2\nc = 3\n")

FINDING = {
    "summary": "Divides without guarding zero",
    "detail": "An empty list raises ZeroDivisionError.",
    "severity": "high",
    "confidence": "certain",
    "line": 2,
}


def _provider(*findings: object) -> FakeProvider:
    return FakeProvider(
        response=CompletionResponse(
            text=json.dumps({"findings": list(findings)}),
            model="fake-model",
            usage=TokenUsage(input_tokens=100, output_tokens=40),
        )
    )


@pytest.mark.unit
def test_a_clean_run_returns_findings_with_their_provenance() -> None:
    analyze = AnalyzeSourceFile(FakeSourceReader(source=SOURCE), _provider(FINDING))

    result = analyze(Path("app.py"))

    assert len(result.findings) == 1
    assert result.findings[0].severity is Severity.HIGH
    assert result.source_path == Path("app.py")
    assert result.model == "fake-model"
    assert result.usage.total_tokens == 140


@pytest.mark.unit
def test_a_file_with_no_defects_is_a_successful_result() -> None:
    analyze = AnalyzeSourceFile(FakeSourceReader(source=SOURCE), _provider())

    result = analyze(Path("app.py"))

    assert result.findings == ()
    assert not result.has_findings


@pytest.mark.unit
def test_the_file_is_read_before_the_provider_is_called() -> None:
    """Reading is free; a provider call costs money. Order matters."""
    reader = FakeSourceReader(error=SourceNotFoundError("no such file"))
    provider = _provider(FINDING)
    analyze = AnalyzeSourceFile(reader, provider)

    with pytest.raises(SourceNotFoundError):
        analyze(Path("missing.py"))

    assert provider.call_count == 0


@pytest.mark.unit
def test_the_prompt_carries_the_numbered_file() -> None:
    provider = _provider(FINDING)
    AnalyzeSourceFile(FakeSourceReader(source=SOURCE), provider)(Path("app.py"))

    user_message = provider.requests[0].messages[-1]
    assert user_message.role is Role.USER
    assert "   1 | a = 1" in user_message.content
    assert "app.py" in user_message.content


@pytest.mark.unit
def test_the_request_is_deterministic() -> None:
    """Analysis, not authorship. The same file should answer the same twice."""
    provider = _provider(FINDING)
    AnalyzeSourceFile(FakeSourceReader(source=SOURCE), provider)(Path("app.py"))

    assert provider.requests[0].temperature == 0.0


@pytest.mark.unit
@pytest.mark.parametrize(
    "error",
    [
        SourceNotFoundError("no such file"),
        SourceTooLargeError("too big"),
    ],
)
def test_a_source_failure_reaches_the_caller_unchanged(error: Exception) -> None:
    """Swallowing it would report "no problems" for a run that never happened."""
    analyze = AnalyzeSourceFile(FakeSourceReader(error=error), _provider())

    with pytest.raises(type(error)):
        analyze(Path("app.py"))


@pytest.mark.unit
def test_a_provider_failure_reaches_the_caller_unchanged() -> None:
    analyze = AnalyzeSourceFile(
        FakeSourceReader(source=SOURCE),
        FakeProvider(error=ProviderRateLimitError("slow down")),
    )

    with pytest.raises(ProviderRateLimitError):
        analyze(Path("app.py"))


@pytest.mark.unit
def test_an_unusable_reply_is_reported_rather_than_returned_empty() -> None:
    """ "No findings" and "could not read the answer" are different outcomes."""
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

    with pytest.raises(ProviderResponseError):
        analyze(Path("app.py"))


@pytest.mark.unit
def test_the_use_case_calls_the_provider_once() -> None:
    """One analysis, one charge. Retries are the caller's decision."""
    provider = _provider(FINDING)
    AnalyzeSourceFile(FakeSourceReader(source=SOURCE), provider)(Path("app.py"))

    assert provider.call_count == 1
