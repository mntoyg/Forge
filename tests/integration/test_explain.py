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
from forge.presentation.json_output import serialize_explanation_json
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
                        "kind": "call",
                        "target": "sum",
                        "start_line": 2,
                        "end_line": 2,
                    }
                ],
            }
        ],
        "flow": [
            {
                "claim": "Calls sum with the supplied values.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "sum",
                        "start_line": 2,
                        "end_line": 2,
                    }
                ],
            }
        ],
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
    assert "Evidence: call target `sum`, lines 2-2" in rendered
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
            },
            {
                "claim": "Sends the explanation request to the configured provider.",
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
def test_explain_omits_compound_symbol_role_with_only_one_cited_action(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, path):\n"
        "        source = self._reader.read(path)\n"
        "        answer = self._provider.complete(source)\n"
        "        return answer\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    claim_text = (
        "PRIVATE_COMPOUND_SYMBOL_CLAIM: Read one safe source snapshot and "
        "request one evidence-backed answer."
    )
    payload = {
        "purpose": [],
        "flow": [],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": claim_text,
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
    provider_response = json.dumps(payload)
    provider = _provider(provider_response)
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("explain.py"))
    rendered = render_explanation(result)
    serialized = serialize_explanation_json(result, "explain.py")
    json_result = json.loads(serialized)

    assert provider.call_count == 1
    assert result.symbols == ()
    assert result.incomplete
    assert result.processing_incomplete is True
    assert (
        "1 symbol claim was omitted because coordinated actions did not have "
        "enough separate cited line ranges."
    ) in rendered
    assert claim_text not in rendered
    assert "PRIVATE_COMPOUND_SYMBOL_CLAIM" not in serialized
    assert "self._reader.read" not in rendered
    assert "self._reader.read" not in serialized
    assert "symbol_action_evidence_insufficient" in serialized
    assert provider_response not in serialized
    assert json_result["completeness"]["status"] == "partial"


@pytest.mark.integration
def test_provider_backed_purpose_reuses_main_flow_call_anchor(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, request):\n"
        "        response = self._provider.complete(request)\n"
        "        return parse_explanation(response.text)\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    provider_call = {
        "kind": "call",
        "target": "self._provider.complete",
        "start_line": 3,
        "end_line": 3,
    }
    payload = {
        "purpose": [
            {
                "claim": "Obtains an explanation from the configured provider.",
                "confidence": "likely",
                "evidence": [provider_call],
            }
        ],
        "flow": [
            {
                "claim": "Sends the request to the configured provider.",
                "confidence": "likely",
                "evidence": [provider_call],
            },
            {
                "claim": "Parses the provider response.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "parse_explanation",
                        "start_line": 4,
                        "end_line": 4,
                    }
                ],
            },
        ],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": "Delegates request completion to the configured provider.",
                "confidence": "likely",
                "evidence": [provider_call],
            }
        ],
        "limitations": [],
        "context_insufficient": False,
    }
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("explain.py"))
    rendered = render_explanation(result)
    system_prompt = " ".join(provider.requests[0].messages[0].content.split())

    assert provider.call_count == 1
    assert "Reuse a Main flow call anchor verbatim:" in system_prompt
    assert "same kind, exact target, and exact" in system_prompt
    assert "If Main flow has no validated call anchor, omit Purpose" in system_prompt
    assert len(result.purpose) == 1
    assert len(result.flow) == 2
    assert len(result.symbols) == 1
    assert "Obtains an explanation from the configured provider." in rendered
    assert "Sends the request to the configured provider." in rendered
    assert "Parses the provider response." in rendered
    assert "Delegates request completion to the configured provider." in rendered
    assert rendered.index("Purpose:") < rendered.index("Main flow:")
    assert rendered.index("Main flow:") < rendered.index("Important symbols:")
    assert "Evidence: call target `self._provider.complete`, lines 3-3" in rendered
    assert "3 |         response = self._provider.complete(request)" in rendered
    assert "Evidence: call target `parse_explanation`, lines 4-4" in rendered
    assert "4 |         return parse_explanation(response.text)" in rendered


@pytest.mark.integration
def test_provider_backed_explanation_omits_bad_purpose_and_keeps_narrow_symbol(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, path):\n"
        "        source = self._reader.read(path)\n"
        "        response = self._provider.complete(source)\n"
        "        return parse_explanation(response.text)\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [
            {
                "claim": "Handles all explanation work.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._provider.explain",
                        "start_line": 4,
                        "end_line": 4,
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
            },
            {
                "claim": "Sends the source to the configured provider.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._provider.complete",
                        "start_line": 4,
                        "end_line": 4,
                    }
                ],
            },
        ],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": "Reads the selected path through the injected reader.",
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
    notes = rendered.split("Analysis notes:\n", 1)[1].split("Incomplete:", 1)[0]

    assert provider.call_count == 1
    system_prompt = provider.requests[0].messages[0].content
    assert "every action or responsibility stated in the claim" in system_prompt
    assert "cite the use site for each action" in system_prompt
    assert result.purpose == ()
    assert len(result.symbols) == 1
    assert result.symbols[0].text == (
        "Reads the selected path through the injected reader."
    )
    assert "target did not match executable tokens in the cited lines" in notes
    assert "Handles all explanation work." not in rendered
    assert "Reads the selected path through the injected reader." in rendered


@pytest.mark.integration
def test_provider_backed_purpose_with_other_valid_call_is_omitted_safely(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, request):\n"
        "        response = self._provider.complete(request)\n"
        "        self._audit.record(response)\n"
        "        return parse_explanation(response.text)\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [
            {
                "claim": "PRIVATE_UNMATCHED_PURPOSE_CLAIM",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._audit.record",
                        "start_line": 4,
                        "end_line": 4,
                    }
                ],
            }
        ],
        "flow": [
            {
                "claim": "Sends the request to the configured provider.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._provider.complete",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
        ],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": "Delegates request completion to the configured provider.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._provider.complete",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
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
    assert result.purpose == ()
    assert len(result.flow) == 1
    assert len(result.symbols) == 1
    assert result.incomplete
    assert (
        "1 purpose claim was omitted because no Purpose call anchor matched a validated Main flow call."
        in notes
    )
    assert "PRIVATE_UNMATCHED_PURPOSE_CLAIM" not in notes
    assert "self._audit.record" not in notes
    assert provider_response not in notes
    assert "Sends the request to the configured provider." in rendered
    assert "Delegates request completion to the configured provider." in rendered
    assert "Evidence: call target `self._provider.complete`, lines 3-3" in rendered


@pytest.mark.integration
def test_provider_backed_purpose_is_omitted_without_valid_main_flow_call(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, request):\n"
        "        response = self._provider.complete(request)\n"
        "        return parse_explanation(response.text)\n"
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
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
        ],
        "flow": [
            {
                "claim": "Assigns the provider response.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "operation",
                        "target": "response = self._provider.complete(request)",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
        ],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": "Delegates request completion to the configured provider.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "self._provider.complete",
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
    assert result.purpose == ()
    assert len(result.flow) == 1
    assert len(result.symbols) == 1
    assert result.incomplete
    assert "Obtains an explanation from the configured provider." not in rendered
    assert "Assigns the provider response." in rendered
    assert "Delegates request completion to the configured provider." in rendered
    assert (
        "1 purpose claim was omitted because no Purpose call anchor matched a validated Main flow call."
        in rendered
    )


@pytest.mark.parametrize(
    ("purpose_evidence", "expected_diagnostic"),
    [
        pytest.param(
            [
                {
                    "kind": "call",
                    "target": "PRIVATE_WRONG_PROVIDER",
                    "start_line": 3,
                    "end_line": 3,
                }
            ],
            "1 purpose claim was omitted because the target did not match executable tokens in the cited lines.",
            id="wrong-target",
        ),
        pytest.param(
            [
                {
                    "kind": "call",
                    "target": "self._provider.complete",
                    "start_line": 2,
                    "end_line": 2,
                }
            ],
            "1 purpose claim was omitted because the target did not match executable tokens in the cited lines.",
            id="wrong-source-range",
        ),
        pytest.param(
            [
                {
                    "kind": "call",
                    "target": "self._provider.complete",
                    "start_line": 99,
                    "end_line": 99,
                }
            ],
            "1 purpose claim was omitted because evidence was malformed or its line range was invalid.",
            id="invalid-line-range",
        ),
        pytest.param(
            [{"kind": "call", "target": "self._provider.complete", "start_line": 3}],
            "1 purpose claim was omitted because evidence was malformed or its line range was invalid.",
            id="malformed-anchor",
        ),
        pytest.param(
            None,
            "1 purpose claim was omitted because evidence was malformed or its line range was invalid.",
            id="no-evidence",
        ),
        pytest.param(
            [
                {
                    "kind": "operation",
                    "target": "response = self._provider.complete(request)",
                    "start_line": 3,
                    "end_line": 3,
                }
            ],
            "1 purpose claim was omitted because no Purpose call anchor matched a validated Main flow call.",
            id="operation-only",
        ),
        pytest.param(
            [
                {
                    "kind": "access",
                    "target": "self._provider",
                    "start_line": 3,
                    "end_line": 3,
                }
            ],
            "1 purpose claim was omitted because no Purpose call anchor matched a validated Main flow call.",
            id="access-only",
        ),
    ],
)
@pytest.mark.integration
def test_provider_backed_purpose_rejects_invalid_call_anchor(
    tmp_path: Path,
    purpose_evidence: list[dict[str, Any]] | None,
    expected_diagnostic: str,
) -> None:
    workspace = tmp_path
    source_text = (
        "class ExplainSource:\n"
        "    def __call__(self, request):\n"
        "        response = self._provider.complete(request)\n"
        "        return parse_explanation(response.text)\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    provider_call = {
        "kind": "call",
        "target": "self._provider.complete",
        "start_line": 3,
        "end_line": 3,
    }
    payload = {
        "purpose": [
            {
                "claim": "PRIVATE_UNSUPPORTED_PURPOSE_CLAIM",
                "confidence": "likely",
                **(
                    {"evidence": purpose_evidence}
                    if purpose_evidence is not None
                    else {}
                ),
            }
        ],
        "flow": [
            {
                "claim": "Sends the request to the configured provider.",
                "confidence": "likely",
                "evidence": [provider_call],
            },
            {
                "claim": "Parses the provider response.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "parse_explanation",
                        "start_line": 4,
                        "end_line": 4,
                    }
                ],
            },
        ],
        "symbols": [
            {
                "symbol": "ExplainSource",
                "claim": "Delegates request completion to the configured provider.",
                "confidence": "likely",
                "evidence": [provider_call],
            }
        ],
        "limitations": [],
        "context_insufficient": False,
    }
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("explain.py"))
    rendered = render_explanation(result)
    notes = rendered.split("Analysis notes:\n", 1)[1].split("Incomplete:", 1)[0]

    assert provider.call_count == 1
    assert result.purpose == ()
    assert len(result.flow) == 2
    assert len(result.symbols) == 1
    assert result.incomplete
    assert expected_diagnostic in notes
    if "no Purpose call anchor" not in expected_diagnostic:
        assert "no Purpose call anchor" not in notes
    assert "PRIVATE_UNSUPPORTED_PURPOSE_CLAIM" not in notes
    assert "PRIVATE_WRONG_PROVIDER" not in notes
    assert "Sends the request to the configured provider." in rendered
    assert "Parses the provider response." in rendered
    assert "Delegates request completion to the configured provider." in rendered
    assert "Evidence: call target `self._provider.complete`, lines 3-3" in rendered
    assert "Evidence: call target `parse_explanation`, lines 4-4" in rendered


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
        "2 symbol claims were omitted because the target did not match executable tokens in the cited lines."
        in notes
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
def test_evidence_diagnostics_name_validator_rules_without_echoing_inputs(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    source_text = (
        "class SafeSubject:\n"
        "    def run(self):\n"
        "        return selected_client.send()\n"
    )
    (workspace / "explain.py").write_bytes(source_text.encode())
    payload = {
        "purpose": [
            {
                "claim": "The selected client is called.",
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
                "claim": "PRIVATE_MALFORMED_EVIDENCE_CLAIM",
                "confidence": "likely",
                "evidence": ["PRIVATE_MALFORMED_EVIDENCE_OBJECT"],
            },
            {
                "claim": "PRIVATE_OUT_OF_RANGE_CLAIM",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "operation",
                        "target": "selected_client.send()",
                        "start_line": 99,
                        "end_line": 99,
                    }
                ],
            },
            {
                "claim": "PRIVATE_TARGET_ABSENT_CLAIM",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "missing_client.send",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
            {
                "claim": "PRIVATE_UNKNOWN_KIND_CLAIM",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "PRIVATE_UNKNOWN_KIND",
                        "target": "selected_client.send",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
            {
                "claim": "PRIVATE_TARGET_SHAPE_CLAIM",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": '"PRIVATE_TARGET_SHAPE"',
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            },
            {
                "claim": "PRIVATE_CALL_DECLARATION_CLAIM",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "run",
                        "start_line": 2,
                        "end_line": 2,
                    }
                ],
            },
        ],
        "flow": [
            {
                "claim": "Calls the selected client.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "selected_client.send",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
        ],
        "symbols": [
            {
                "symbol": "SafeSubject",
                "claim": "PRIVATE_SYMBOL_OPERATION_CLAIM",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "operation",
                        "target": "return selected_client.send()",
                        "start_line": 3,
                        "end_line": 3,
                    }
                ],
            }
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
    assert len(result.purpose) == 1
    assert result.purpose[0].text == "The selected client is called."
    assert "The selected client is called." in rendered
    assert "Evidence: call target `selected_client.send`, lines 3-3" in rendered
    assert "3 |         return selected_client.send()" in rendered
    assert (
        "2 purpose claims were omitted because evidence was malformed or its line range was invalid."
        in notes
    )
    assert (
        "1 purpose claim was omitted because the anchor kind was unsupported." in notes
    )
    assert (
        "1 purpose claim was omitted because the target shape was unsupported." in notes
    )
    assert (
        "1 purpose claim was omitted because the target did not match executable tokens in the cited lines."
        in notes
    )
    assert (
        "1 purpose claim was omitted because the call target matched a function declaration, not a call expression."
        in notes
    )
    assert (
        "1 symbol claim was omitted because symbol claims cannot use operation anchors."
        in notes
    )
    for private_value in (
        "PRIVATE_MALFORMED_EVIDENCE_CLAIM",
        "PRIVATE_MALFORMED_EVIDENCE_OBJECT",
        "PRIVATE_OUT_OF_RANGE_CLAIM",
        "PRIVATE_TARGET_ABSENT_CLAIM",
        "PRIVATE_UNKNOWN_KIND_CLAIM",
        "PRIVATE_UNKNOWN_KIND",
        "PRIVATE_TARGET_SHAPE_CLAIM",
        '"PRIVATE_TARGET_SHAPE"',
        "PRIVATE_CALL_DECLARATION_CLAIM",
        "PRIVATE_SYMBOL_OPERATION_CLAIM",
        "SafeSubject",
        source_text,
        provider_response,
    ):
        assert private_value not in notes


@pytest.mark.integration
def test_valid_call_anchor_is_rendered_without_rejection_diagnostic(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    (workspace / "app.py").write_bytes(b"client.send()\n")
    payload = {
        "purpose": [
            {
                "claim": "Sends the request through the client.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "client.send",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
            }
        ],
        "flow": [
            {
                "claim": "Sends the request through the client.",
                "confidence": "likely",
                "evidence": [
                    {
                        "kind": "call",
                        "target": "client.send",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
            }
        ],
        "symbols": [],
        "limitations": [],
        "context_insufficient": False,
    }
    provider = _provider(json.dumps(payload))
    use_case = ExplainSource(FilesystemSourceReader(workspace), provider)

    result = use_case(Path("app.py"))
    rendered = render_explanation(result)
    notes = rendered.split("Analysis notes:\n", 1)[1].split("Incomplete:", 1)[0]

    assert provider.call_count == 1
    assert len(result.purpose) == 1
    assert "Sends the request through the client." in rendered
    assert "Evidence: call target `client.send`, lines 1-1" in rendered
    assert "purpose claim was omitted" not in notes
    assert "evidence was malformed" not in notes


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
