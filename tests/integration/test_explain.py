import io
import json
from pathlib import Path
from typing import Any

import pytest

from forge.application.explain import ExplainSource
from forge.domain.ai import CompletionResponse, TokenUsage
from forge.domain.errors import SourceTooLargeError
from forge.infrastructure.source import FilesystemSourceReader
from forge.presentation.explanation import render_explanation
from tests.support.fakes import FakeProvider


class _RecordingBytesIO(io.BytesIO):
    def __init__(self, value: bytes, sizes: list[int | None]) -> None:
        super().__init__(value)
        self._sizes = sizes

    def read(self, size: int | None = -1) -> bytes:
        self._sizes.append(size)
        return super().read(size)


def _provider(response_text: str) -> FakeProvider:
    return FakeProvider(
        response=CompletionResponse(
            text=response_text,
            model="fake-model",
            usage=TokenUsage(input_tokens=12, output_tokens=8),
        )
    )


@pytest.mark.integration
def test_explanation_cites_excerpts_from_the_submitted_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = "def total(values):\n    return sum(values)\n"
    (workspace / "app.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [
            {
                "claim": "Returns the sum of values.",
                "confidence": "certain",
                "evidence": [
                    {
                        "kind": "return_value",
                        "target": "sum(values)",
                        "start_line": 2,
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
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("app.py"))
    rendered = render_explanation(result)

    assert provider.call_count == 1
    assert "1 | def total(values):" in provider.requests[0].messages[1].content
    assert "Evidence: return_value target `sum(values)`, lines 2-2" in rendered
    assert "2 |     return sum(values)" in rendered


@pytest.mark.integration
def test_explain_claims_use_distinct_responsibility_evidence_from_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, path):\n"
        "        source = self._reader.read(path)\n"
        "        request = build_explain_request(source)\n"
        "        response = self._provider.complete(request)\n"
        "        result = parse_explanation(response.text, source)\n"
        "        return result\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [
            {
                "claim": "Obtains an explanation from the configured provider.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._provider.complete",
                        "start_line": 5,
                        "end_line": 5,
                    }
                ],
            }
        ],
        "flow": [
            {
                "claim": "Reads the selected source through the injected reader.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._reader.read",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
        ],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": "Reads the selected source through the injected reader.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._reader.read",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
            {
                "symbol": "ExplainSource",
                "claim": "Builds the provider request from the selected source snapshot.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "build_explain_request",
                        "start_line": 4,
                        "end_line": 4,
                    }
                ],
            },
            {
                "symbol": "ExplainSource",
                "claim": "Delegates the explanation request to the configured provider.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._provider.complete",
                        "start_line": 5,
                        "end_line": 5,
                    }
                ],
            },
            {
                "symbol": "ExplainSource",
                "claim": "Parses the provider response against the submitted source snapshot.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "parse_explanation",
                        "start_line": 6,
                        "end_line": 6,
                    }
                ],
            },
            {
                "symbol": "ExplainSource",
                "claim": "Performs an extra validation pass after parsing.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "validate_again",
                        "start_line": 6,
                        "end_line": 6,
                    }
                ],
            },
        ],
        "limitations": [],
        "context_insufficient": False,
    }
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("explain.py"))
    rendered = render_explanation(result)

    assert provider.call_count == 1
    submitted = provider.requests[0].messages[1].content
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        assert f"{line_number:>4} | {line}" in submitted
    assert len(result.symbols) == 4
    assert all(claim.symbol == "ExplainSource" for claim in result.symbols)
    assert result.incomplete
    assert "Obtains an explanation from the configured provider." in rendered
    assert "Evidence: call target `self._provider.complete`, lines 5-5" in rendered
    assert "5 |         response = self._provider.complete(request)" in rendered
    assert "Reads the selected source through the injected reader." in rendered
    assert "Evidence: call target `self._reader.read`, lines 3-3" in rendered
    assert "3 |         source = self._reader.read(path)" in rendered
    assert "Builds the provider request from the selected source snapshot." in rendered
    assert "Evidence: call target `build_explain_request`, lines 4-4" in rendered
    assert "4 |         request = build_explain_request(source)" in rendered
    assert "Delegates the explanation request to the configured provider." in rendered
    assert (
        "Parses the provider response against the submitted source snapshot."
        in rendered
    )
    assert "Evidence: call target `parse_explanation`, lines 6-6" in rendered
    assert "6 |         result = parse_explanation(response.text, source)" in rendered
    assert "Performs an extra validation pass after parsing." not in rendered


@pytest.mark.integration
def test_explain_rejects_method_declaration_as_provider_call_evidence(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, path):\n"
        "        return None\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [
            {
                "claim": "Obtains an explanation from the configured provider.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "__call__",
                        "start_line": 2,
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
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("explain.py"))
    rendered = render_explanation(result)

    assert provider.call_count == 1
    assert result.purpose == ()
    assert result.incomplete
    assert "Obtains an explanation from the configured provider." not in rendered


@pytest.mark.integration
def test_explanation_diagnostics_report_empty_sections_without_rejection_claims(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    (workspace / "app.py").write_bytes(b"a = 1\n")
    payload = {
        "purpose": [],
        "flow": [
            {
                "claim": "Assigns the initial value.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "operation",
                        "target": "a = 1",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
            }
        ],
        "symbols": [],
        "limitations": [],
        "context_insufficient": True,
    }
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("app.py"))
    rendered = render_explanation(result)

    assert provider.call_count == 1
    assert result.flow
    assert "No claims were returned for Purpose." in rendered
    assert "No claims were returned for Important symbols." in rendered
    assert "claim was omitted because" not in rendered
    assert "The provider reported that context was insufficient." in rendered


@pytest.mark.integration
def test_explanation_diagnostics_distinguish_missing_and_malformed_sections(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    (workspace / "app.py").write_bytes(b"a = 1\n")
    payload = {
        "flow": [
            {
                "claim": "Assigns the initial value.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "operation",
                        "target": "a = 1",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
            }
        ],
        "symbols": "PRIVATE_MALFORMED_SYMBOL_SECTION",
        "limitations": "PRIVATE_MALFORMED_LIMITATIONS",
        "context_insufficient": False,
    }
    provider_response = json.dumps(payload)
    provider = _provider(provider_response)
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("app.py"))
    rendered = render_explanation(result)
    notes = rendered.split("Analysis notes:\n", 1)[1].split("Incomplete:", 1)[0]

    assert provider.call_count == 1
    assert "The Purpose section was missing." in notes
    assert "The Important symbols section was malformed" in notes
    assert "The limitations field was malformed." in notes
    assert "PRIVATE_MALFORMED_SYMBOL_SECTION" not in notes
    assert "PRIVATE_MALFORMED_LIMITATIONS" not in notes
    assert provider_response not in notes


@pytest.mark.integration
def test_explanation_diagnostics_are_counted_and_never_echo_provider_content(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class SafeSubject:\n"
        "    def run(self):\n"
        "        return selected_client.send()\n"
        "class OtherSubject:\n"
        "    def run(self):\n"
        "        return foreign_client.send()\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [],
        "flow": [],
        "symbols": [
            {
                "claim": "PRIVATE_CLAIM_MISSING_SUBJECT",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "selected_client.send",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
            {
                "symbol": "SafeSubject",
                "claim": "PRIVATE_CLAIM_INVALID_EVIDENCE",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "PRIVATE_ANCHOR_TARGET",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
            {
                "symbol": "SafeSubject",
                "claim": "PRIVATE_CLAIM_SECOND_INVALID_EVIDENCE",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "PRIVATE_SECOND_ANCHOR_TARGET",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
            {
                "symbol": "SafeSubject",
                "claim": "PRIVATE_CLAIM_OUT_OF_SCOPE",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "foreign_client.send",
                        "start_line": 6,
                        "end_line": 6,
                    }
                ],
            },
            {
                "symbol": "SafeSubject",
                "claim": "SafeSubject class",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "selected_client.send",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
        ],
        "limitations": [],
        "context_insufficient": False,
    }
    provider_response = json.dumps(payload)
    provider = _provider(provider_response)
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("explain.py"))
    rendered = render_explanation(result)
    notes = rendered.split("Analysis notes:\n", 1)[1].split("Incomplete:", 1)[0]

    assert provider.call_count == 1
    assert result.incomplete
    assert result.purpose == result.flow == result.symbols == ()
    assert "No claims were returned for Purpose." in notes
    assert "No claims were returned for Main flow." in notes
    assert (
        "1 symbol claim was omitted because a unique subject could not be resolved."
        in notes
    )
    assert (
        "2 symbol claims were omitted because evidence could not be validated." in notes
    )
    assert (
        "1 symbol claim was omitted because evidence fell outside the declared subject scope."
        in notes
    )
    assert (
        "1 symbol claim was omitted because the claim only repeated the symbol name."
        in notes
    )
    for private_value in (
        "PRIVATE_CLAIM_MISSING_SUBJECT",
        "PRIVATE_CLAIM_INVALID_EVIDENCE",
        "PRIVATE_CLAIM_SECOND_INVALID_EVIDENCE",
        "PRIVATE_CLAIM_OUT_OF_SCOPE",
        "SafeSubject",
        "OtherSubject",
        "PRIVATE_ANCHOR_TARGET",
        "PRIVATE_SECOND_ANCHOR_TARGET",
        "selected_client.send",
        "foreign_client.send",
        source_text,
        provider_response,
    ):
        assert private_value not in notes


@pytest.mark.integration
def test_explain_omits_unrelated_symbol_with_a_valid_call_site(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, path):\n"
        "        return self._reader.read(path)\n"
        "class OtherThing:\n"
        "    def read(self):\n"
        "        return self._provider.complete()\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [],
        "flow": [],
        "symbols": [
            {
                "symbol": "OtherThing",
                "claim": "OtherThing coordinates the selected source read.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._reader.read",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
        ],
        "limitations": [],
        "context_insufficient": False,
    }
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("explain.py"))
    rendered = render_explanation(result)

    assert provider.call_count == 1
    assert result.symbols == ()
    assert result.incomplete
    assert "OtherThing coordinates" not in rendered
    assert "Important symbols:\n  None identified." in rendered
    assert "Incomplete:" in rendered


@pytest.mark.integration
def test_growth_after_preflight_is_bounded_and_makes_no_provider_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path
    source_path = workspace / "app.py"
    source_path.write_bytes(b"x = 1\n")
    max_bytes = 16
    original_open = Path.open
    read_sizes: list[int | None] = []
    provider = _provider("{}")

    def grow_before_read(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if path == source_path and mode == "rb":
            grown_content = b"x" * (max_bytes * 20)
            with original_open(path, "wb") as stream:
                stream.write(grown_content)
            return _RecordingBytesIO(grown_content, read_sizes)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_before_read)

    with pytest.raises(SourceTooLargeError, match="grew beyond"):
        ExplainSource(FilesystemSourceReader(workspace, max_bytes=max_bytes), provider)(
            Path("app.py")
        )

    assert read_sizes == [max_bytes + 1]
    assert provider.call_count == 0
    assert source_path.stat().st_size == max_bytes * 20
