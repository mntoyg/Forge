import json
from pathlib import Path

import pytest

from forge.application.explain_parsing import (
    _INFORMATIONAL_DIAGNOSTICS,
    _OMISSION_DIAGNOSTICS,
    _VALIDATION_UNAVAILABLE_DIAGNOSTICS,
    _WARNING_DIAGNOSTICS,
    _processing_incomplete,
    parse_explanation,
)
from forge.domain.ai import TokenUsage
from forge.domain.errors import ProviderResponseError
from forge.domain.explanation import (
    EvidenceKind,
    ExplanationDiagnostic,
    ExplanationDiagnosticKind,
    ExplanationSection,
)
from forge.domain.source import SourceFile
from forge.presentation.explanation import render_explanation


def _payload(*claims: object, flow: list[object] | None = None) -> dict[str, object]:
    return {
        "purpose": list(claims),
        "flow": flow or [],
        "symbols": [],
        "limitations": [],
        "context_insufficient": False,
    }


def _claim(
    start: object = 1,
    end: object = 2,
    target: str = "a = 1",
    *,
    call_target: str | None = None,
    call_line: int | None = None,
) -> dict[str, object]:
    evidence: list[object] = [
        {
            "kind": "operation",
            "target": target,
            "start_line": start,
            "end_line": end,
        }
    ]
    if call_target is not None and call_line is not None:
        evidence.append(
            {
                "kind": "call",
                "target": call_target,
                "start_line": call_line,
                "end_line": call_line,
            }
        )
    return {
        "claim": "Calculates a total.",
        "confidence": "likely",
        "evidence": evidence,
    }


def _flow_call(target: str, line: int) -> dict[str, object]:
    return {
        "claim": "Calls the configured client.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "call",
                "target": target,
                "start_line": line,
                "end_line": line,
            }
        ],
    }


def test_evidence_kind_remains_a_string_enum() -> None:
    assert EvidenceKind("call") is EvidenceKind.CALL
    assert isinstance(EvidenceKind.CALL, str)


def test_every_diagnostic_kind_has_one_completeness_classification() -> None:
    classifications = (
        _OMISSION_DIAGNOSTICS,
        _WARNING_DIAGNOSTICS,
        _INFORMATIONAL_DIAGNOSTICS,
        _VALIDATION_UNAVAILABLE_DIAGNOSTICS,
    )

    assert set().union(*classifications) == set(ExplanationDiagnosticKind)
    assert sum(len(group) for group in classifications) == len(
        set().union(*classifications)
    )
    assert all(
        _processing_incomplete((ExplanationDiagnostic(None, kind),)) is True
        for kind in _OMISSION_DIAGNOSTICS
    )
    assert all(
        _processing_incomplete((ExplanationDiagnostic(None, kind),)) is None
        for kind in _VALIDATION_UNAVAILABLE_DIAGNOSTICS
    )
    assert all(
        _processing_incomplete((ExplanationDiagnostic(None, kind),)) is False
        for kind in _WARNING_DIAGNOSTICS | _INFORMATIONAL_DIAGNOSTICS
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [(0, 1), (3, 3), (2, 1), (True, 1), (1, False), ("1", 2)],
)
def test_invalid_evidence_ranges_are_discarded_and_marked_incomplete(
    start: object, end: object
) -> None:
    source = SourceFile(Path("app.py"), "a = 1\nb = 2\n")

    result = parse_explanation(
        json.dumps(_payload(_claim(start, end))),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete
    assert result.processing_incomplete is True
    assert any(
        diagnostic.kind in _OMISSION_DIAGNOSTICS for diagnostic in result.diagnostics
    )


def test_missing_evidence_is_discarded_and_context_gap_is_visible() -> None:
    source = SourceFile(Path("app.py"), "a = 1\n")
    invalid = {"claim": "Unsupported", "confidence": "likely"}
    payload = _payload(invalid)
    payload["context_insufficient"] = True

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.purpose == ()
    assert result.incomplete
    assert result.context_insufficient
    assert result.limitations
    assert result.processing_incomplete is True


def test_valid_one_based_range_is_preserved() -> None:
    source = SourceFile(Path("app.py"), "a = 1\nb = 2\nclient.send()\n")

    result = parse_explanation(
        json.dumps(
            _payload(
                _claim(call_target="client.send", call_line=3),
                flow=[_flow_call("client.send", 3)],
            )
        ),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose[0].evidence[0].start_line == 1
    assert result.purpose[0].evidence[0].end_line == 2
    assert result.purpose[0].evidence[0].kind.value == "operation"
    assert result.purpose[0].evidence[0].target == "a = 1"
    assert not result.incomplete
    assert result.processing_incomplete is False


@pytest.mark.parametrize(
    ("evidence", "expected_kind"),
    [
        (None, ExplanationDiagnosticKind.EVIDENCE_MALFORMED),
        (
            [
                {
                    "kind": "operation",
                    "target": "response = self._reader.send()",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
            ExplanationDiagnosticKind.PURPOSE_CALL_NOT_IN_FLOW,
        ),
        (
            [
                {
                    "kind": "access",
                    "target": "self._reader",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
            ExplanationDiagnosticKind.PURPOSE_CALL_NOT_IN_FLOW,
        ),
        (
            [
                {
                    "kind": "operation",
                    "target": "response = self._reader.send()",
                    "start_line": 1,
                    "end_line": 1,
                },
                {
                    "kind": "call",
                    "target": "other.send",
                    "start_line": 1,
                    "end_line": 1,
                },
            ],
            ExplanationDiagnosticKind.EVIDENCE_TARGET_NOT_FOUND,
        ),
    ],
    ids=("no-evidence", "operation-only", "access-only", "invalid-call"),
)
def test_purpose_requires_a_validated_call_shared_with_flow(
    evidence: list[dict[str, object]] | None,
    expected_kind: ExplanationDiagnosticKind,
) -> None:
    source = SourceFile(Path("app.py"), "response = self._reader.send()\n")
    claim: dict[str, object] = {
        "claim": "Uses the client to produce a response.",
        "confidence": "likely",
    }
    if evidence is not None:
        claim["evidence"] = evidence
    payload = _payload(
        claim,
        flow=[_flow_call("self._reader.send", 1)],
    )

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.purpose == ()
    assert result.incomplete
    purpose_diagnostics = tuple(
        diagnostic.kind
        for diagnostic in result.diagnostics
        if diagnostic.section is ExplanationSection.PURPOSE
        and diagnostic.kind is not ExplanationDiagnosticKind.SECTION_EMPTY
    )
    assert purpose_diagnostics == (expected_kind,)


def test_empty_sections_are_distinguished_from_rejected_claims() -> None:
    source = SourceFile(Path("app.py"), "a = 1\nb = 2\n")
    payload = _payload()
    payload["purpose"] = []
    payload["flow"] = [_claim()]
    payload["symbols"] = []

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert not result.incomplete
    assert result.processing_incomplete is False
    assert [
        (diagnostic.section, diagnostic.kind, diagnostic.count)
        for diagnostic in result.diagnostics
    ] == [
        (ExplanationSection.PURPOSE, ExplanationDiagnosticKind.SECTION_EMPTY, 1),
        (ExplanationSection.SYMBOLS, ExplanationDiagnosticKind.SECTION_EMPTY, 1),
    ]


def test_context_insufficiency_alone_keeps_processing_completeness_known() -> None:
    source = SourceFile(Path("app.py"), "a = 1\n")
    payload = _payload()
    payload["context_insufficient"] = True

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.incomplete
    assert result.context_insufficient
    assert result.processing_incomplete is False
    assert any(
        diagnostic.kind is ExplanationDiagnosticKind.CONTEXT_INSUFFICIENT
        for diagnostic in result.diagnostics
    )
    assert not any(
        diagnostic.kind in _OMISSION_DIAGNOSTICS for diagnostic in result.diagnostics
    )


def test_valid_limitations_alone_are_not_processing_omissions() -> None:
    source = SourceFile(Path("app.py"), "a = 1\n")
    payload = _payload()
    payload["limitations"] = ["Behavior depends on runtime configuration."]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.incomplete
    assert result.limitations == ("Behavior depends on runtime configuration.",)
    assert result.processing_incomplete is False
    assert not any(
        diagnostic.kind in _OMISSION_DIAGNOSTICS for diagnostic in result.diagnostics
    )


def test_malformed_limitation_entries_are_known_field_omissions() -> None:
    source = SourceFile(Path("app.py"), "a = 1\n")
    payload = _payload()
    payload["limitations"] = [None, ""]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.processing_incomplete is True
    assert (
        None,
        ExplanationDiagnosticKind.LIMITATIONS_MALFORMED,
        2,
    ) in tuple(
        (diagnostic.section, diagnostic.kind, diagnostic.count)
        for diagnostic in result.diagnostics
    )


def test_retained_claim_with_downgraded_confidence_is_not_an_omission() -> None:
    source = SourceFile(Path("app.py"), "a = 1\nclient.send()\n")
    claim = _claim(call_target="client.send", call_line=2)
    claim["confidence"] = "unrecognized"

    result = parse_explanation(
        json.dumps(_payload(claim, flow=[_flow_call("client.send", 2)])),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.incomplete
    assert result.purpose[0].confidence.value == "possible"
    assert result.processing_incomplete is False
    assert any(
        diagnostic.kind is ExplanationDiagnosticKind.CONFIDENCE_UNRECOGNIZED
        for diagnostic in result.diagnostics
    )


def test_non_python_empty_sections_make_validation_unknown_not_partial() -> None:
    source = SourceFile(Path("app.ts"), "const count = 1;\n")

    result = parse_explanation(
        json.dumps(_payload()), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.incomplete
    assert result.processing_incomplete is None
    assert any(
        diagnostic.kind is ExplanationDiagnosticKind.SOURCE_VALIDATION_UNAVAILABLE
        for diagnostic in result.diagnostics
    )
    assert not any(
        diagnostic.kind in _OMISSION_DIAGNOSTICS for diagnostic in result.diagnostics
    )


def test_python_tokenization_failure_without_claims_is_unknown() -> None:
    source = SourceFile(Path("app.py"), "value = (\n")

    result = parse_explanation(
        json.dumps(_payload()), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.processing_incomplete is None
    assert any(
        diagnostic.kind is ExplanationDiagnosticKind.SOURCE_VALIDATION_UNAVAILABLE
        for diagnostic in result.diagnostics
    )


def test_python_ast_unavailable_without_symbols_is_unknown() -> None:
    source = SourceFile(Path("app.py"), "class Example:\n    if:\n")

    result = parse_explanation(
        json.dumps(_payload()), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.processing_incomplete is None
    assert any(
        diagnostic.kind is ExplanationDiagnosticKind.SYMBOL_VALIDATION_UNAVAILABLE
        for diagnostic in result.diagnostics
    )


def test_missing_limitations_remains_an_incomplete_result() -> None:
    source = SourceFile(Path("app.py"), "a = 1\nb = 2\nclient.send()\n")
    payload = _payload(
        _claim(call_target="client.send", call_line=3),
        flow=[_flow_call("client.send", 3)],
    )
    payload.pop("limitations")

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.incomplete
    assert result.purpose
    assert result.limitations == ()
    assert result.processing_incomplete is True
    assert (None, ExplanationDiagnosticKind.LIMITATIONS_MISSING, 1) in tuple(
        (diagnostic.section, diagnostic.kind, diagnostic.count)
        for diagnostic in result.diagnostics
    )


def test_missing_and_malformed_metadata_sections_are_reported_safely() -> None:
    source = SourceFile(Path("app.py"), "a = 1\nb = 2\n")
    payload = _payload(_claim())
    del payload["purpose"]
    payload["symbols"] = "PRIVATE_SYMBOL_SECTION"
    payload.pop("limitations")
    payload.pop("context_insufficient")

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.incomplete
    assert result.context_insufficient
    assert result.limitations == ()
    assert result.processing_incomplete is True
    assert [
        (diagnostic.section, diagnostic.kind, diagnostic.count)
        for diagnostic in result.diagnostics
    ] == [
        (ExplanationSection.PURPOSE, ExplanationDiagnosticKind.SECTION_MISSING, 1),
        (ExplanationSection.FLOW, ExplanationDiagnosticKind.SECTION_EMPTY, 1),
        (ExplanationSection.SYMBOLS, ExplanationDiagnosticKind.SECTION_MALFORMED, 1),
        (None, ExplanationDiagnosticKind.LIMITATIONS_MISSING, 1),
        (None, ExplanationDiagnosticKind.CONTEXT_STATUS_MISSING, 1),
    ]
    assert "PRIVATE_SYMBOL_SECTION" not in repr(result.diagnostics)


def test_malformed_context_and_limitations_are_not_guessed_as_content_gaps() -> None:
    source = SourceFile(Path("app.py"), "a = 1\nb = 2\n")
    payload = _payload(_claim())
    payload["limitations"] = "PRIVATE_LIMITATIONS_VALUE"
    payload["context_insufficient"] = "PRIVATE_CONTEXT_VALUE"

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.incomplete
    assert result.context_insufficient
    assert result.limitations == ()
    assert result.processing_incomplete is True
    assert [
        (diagnostic.section, diagnostic.kind, diagnostic.count)
        for diagnostic in result.diagnostics
        if diagnostic.section is None
    ] == [
        (None, ExplanationDiagnosticKind.LIMITATIONS_FIELD_MALFORMED, 1),
        (None, ExplanationDiagnosticKind.CONTEXT_STATUS_MALFORMED, 1),
    ]
    assert "This file alone does not provide enough context" not in repr(result)
    assert "PRIVATE_" not in repr(result.diagnostics)


def test_claim_is_counted_once_under_its_first_evidence_rejection() -> None:
    source = SourceFile(Path("app.py"), "client.send()\n")
    claim = {
        "claim": "Calls the client.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "unknown-kind",
                "target": "missing.call",
                "start_line": 1,
                "end_line": 1,
            },
            {
                "kind": "call",
                "target": "client.send",
                "start_line": 99,
                "end_line": 99,
            },
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.incomplete
    purpose_rejections = tuple(
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.section is ExplanationSection.PURPOSE
        and diagnostic.kind is not ExplanationDiagnosticKind.SECTION_EMPTY
    )
    assert len(purpose_rejections) == 1
    assert (
        purpose_rejections[0].kind
        is ExplanationDiagnosticKind.EVIDENCE_KIND_UNSUPPORTED
    )
    assert purpose_rejections[0].count == 1


def test_model_certain_confidence_is_capped_at_likely() -> None:
    source = SourceFile(Path("app.py"), "total = sum(values)\nclient.send()\n")
    claim = _claim(
        1,
        1,
        target="total = sum(values)",
        call_target="client.send",
        call_line=2,
    )
    claim["confidence"] = "certain"

    result = parse_explanation(
        json.dumps(_payload(claim, flow=[_flow_call("client.send", 2)])),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose[0].confidence.value == "likely"


@pytest.mark.parametrize(
    "anchor",
    [
        {
            "kind": "call",
            "target": "missing.call",
            "start_line": 4,
            "end_line": 4,
        },
        {
            "kind": "call",
            "target": "self._provider.complete",
            "start_line": 3,
            "end_line": 3,
        },
        {
            "kind": "return_type",
            "target": "ExplanationResult",
            "start_line": 1,
            "end_line": 1,
        },
        {
            "kind": "return_value",
            "target": "parse_result",
            "start_line": 6,
            "end_line": 6,
        },
        {
            "kind": "unknown",
            "target": "self._provider.complete",
            "start_line": 4,
            "end_line": 4,
        },
    ],
)
def test_invalid_or_mismatched_anchor_is_discarded_and_marks_incomplete(
    anchor: dict[str, object],
) -> None:
    source = SourceFile(
        Path("explain.py"),
        "from forge.domain.explanation import ExplanationResult\n"
        "def explain() -> ExplanationResult:\n"
        "    self._provider = provider\n"
        "    response = self._provider.complete()\n"
        "    return parse_result(response)\n"
        ")\n",
    )
    claim = {
        "claim": "The selected operation produces an explanation.",
        "confidence": "likely",
        "evidence": [anchor],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


def test_operation_anchor_cannot_support_a_symbol_role() -> None:
    source = SourceFile(
        Path("app.py"),
        "class Provider:\n" "    def run(self):\n" "        run_provider()\n",
    )
    payload = _payload()
    payload["symbols"] = [
        {
            "symbol": "Provider",
            "claim": "The provider performs the operation.",
            "confidence": "likely",
            "evidence": [
                {
                    "kind": "operation",
                    "target": "run_provider()",
                    "start_line": 1,
                    "end_line": 1,
                }
            ],
        }
    ]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.symbols == ()
    assert result.incomplete


@pytest.mark.parametrize(
    ("line", "kind", "target"),
    [
        ('"""client.call()"""', "call", "client.call"),
        ("# def explain() -> Result", "return_type", "Result"),
        ('"return make_result()"', "return_value", "make_result"),
        (
            ")",
            "call",
            "make_result",
        ),
    ],
)
def test_non_code_and_delimiter_lines_cannot_satisfy_typed_anchors(
    line: str, kind: str, target: str
) -> None:
    source = SourceFile(Path("app.py"), line + "\n")
    claim = {
        "claim": "The source performs an operation.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": kind,
                "target": target,
                "start_line": 1,
                "end_line": 1,
            }
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


@pytest.mark.parametrize(
    ("line", "kind", "target"),
    [
        ("client.complete()", "call", "client.complete"),
        ("def explain() -> Result:", "return_type", "Result"),
        ("return make_result()", "return_value", "make_result"),
        ("self._reader.value", "access", "self._reader.value"),
        ("client.complete()", "operation", "client.complete()"),
    ],
)
def test_multiline_docstring_body_cannot_satisfy_typed_anchors(
    line: str, kind: str, target: str
) -> None:
    source = SourceFile(Path("app.py"), f'"""Module docs.\n{line}\n"""\n')
    claim = {
        "claim": "The source performs an operation.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": kind,
                "target": target,
                "start_line": 2,
                "end_line": 2,
            }
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


@pytest.mark.parametrize(
    ("source_text", "kind", "target"),
    [
        ("result = 1  # client.complete()\n", "call", "client.complete"),
        ('message = "return make_result()"\n', "return_value", "make_result"),
        ('message = "client.complete()"\n', "operation", "client.complete()"),
        ('message = "self._reader.value"\n', "access", "self._reader.value"),
        ('message = "def run() -> Result:"\n', "return_type", "Result"),
    ],
)
def test_inline_comments_and_strings_cannot_satisfy_typed_anchors(
    source_text: str, kind: str, target: str
) -> None:
    source = SourceFile(Path("app.py"), source_text)
    claim = {
        "claim": "The source performs an operation.",
        "confidence": "likely",
        "evidence": [{"kind": kind, "target": target, "start_line": 1, "end_line": 1}],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


def test_call_target_must_match_the_complete_identifier() -> None:
    source = SourceFile(Path("app.py"), "client.complete_request()\n")
    claim = {
        "claim": "Calls the completion function.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "call",
                "target": "client.complete",
                "start_line": 1,
                "end_line": 1,
            }
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


def test_call_anchor_rejects_a_function_declaration() -> None:
    source = SourceFile(Path("app.py"), "def run():\n    pass\n")
    claim = {
        "claim": "Runs the operation.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "call",
                "target": "run",
                "start_line": 1,
                "end_line": 1,
            }
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


def test_operation_target_must_match_complete_tokens() -> None:
    source = SourceFile(Path("app.py"), "client.complete_request()\n")
    claim = {
        "claim": "Calls the completion function.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "operation",
                "target": "client.complete",
                "start_line": 1,
                "end_line": 1,
            }
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


@pytest.mark.parametrize(
    ("source_text", "line", "target"),
    [
        ("import client.complete\n", 1, "client.complete"),
        ("def method(value: module.Result):\n    pass\n", 1, "module.Result"),
        ("self._reader = reader\n", 1, "self._reader"),
    ],
)
def test_access_anchor_rejects_import_and_assignment_left_hand_side(
    source_text: str, line: int, target: str
) -> None:
    source = SourceFile(Path("app.py"), source_text)
    claim = {
        "claim": "The reader provides a value.",
        "confidence": "likely",
        "evidence": [
            {"kind": "access", "target": target, "start_line": line, "end_line": line}
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose == ()
    assert result.incomplete


def test_access_anchor_accepts_a_read_site() -> None:
    source = SourceFile(Path("app.py"), "value = self._reader.value\nclient.send()\n")
    claim = {
        "claim": "The reader supplies the value.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "access",
                "target": "self._reader.value",
                "start_line": 1,
                "end_line": 1,
            },
            {
                "kind": "call",
                "target": "client.send",
                "start_line": 2,
                "end_line": 2,
            },
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim, flow=[_flow_call("client.send", 2)])),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert len(result.purpose) == 1
    assert not result.incomplete


def test_non_python_source_is_preserved_but_anchors_are_marked_unverified() -> None:
    source = SourceFile(Path("app.ts"), "client.complete()\n")
    claim = {
        "claim": "Calls the client.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "call",
                "target": "client.complete",
                "start_line": 1,
                "end_line": 1,
            }
        ],
    }

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.source is source
    assert result.purpose == ()
    assert result.incomplete
    assert result.processing_incomplete is True
    assert any(
        diagnostic.kind in _OMISSION_DIAGNOSTICS for diagnostic in result.diagnostics
    )


def test_symbol_that_only_repeats_its_name_is_discarded() -> None:
    source = SourceFile(
        Path("app.py"),
        "class ExplainSource:\n"
        "    def __call__(self):\n"
        "        return self._reader.read()\n",
    )
    payload = _payload()
    payload["symbols"] = [
        {
            "symbol": "ExplainSource",
            "claim": "ExplainSource class",
            "confidence": "certain",
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
            "claim": "Coordinates the source read and provider request",
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
    ]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert len(result.symbols) == 1
    assert "Coordinates" in result.symbols[0].text
    assert result.incomplete


@pytest.mark.parametrize(
    ("symbol", "claim_text", "source_text", "target", "line"),
    [
        (
            "OtherThing",
            "OtherThing reads a selected source.",
            "class ExplainSource:\n"
            "    def __call__(self):\n"
            "        return self._reader.read()\n"
            "class OtherThing:\n"
            "    def read(self):\n"
            "        return self._provider.complete()\n",
            "self._reader.read",
            3,
        ),
        (
            "MissingThing",
            "MissingThing reads a selected source.",
            "class ExplainSource:\n"
            "    def __call__(self):\n"
            "        return self._reader.read()\n",
            "self._reader.read",
            3,
        ),
        (
            "ExplainSource",
            "ExplainSource reads a selected source.",
            "class ExplainSource:\n"
            "    def __call__(self):\n"
            "        return self._reader.read()\n"
            "class OtherThing:\n"
            "    def read(self):\n"
            "        return self._provider.complete()\n",
            "self._provider.complete",
            6,
        ),
        (
            "ExplainSource",
            "ExplainSource reads a selected source.",
            "class ExplainSource:\n"
            "    def __call__(self):\n"
            "        return self._reader.read()\n"
            "class ExplainSource:\n"
            "    def __call__(self):\n"
            "        return self._provider.complete()\n",
            "self._reader.read",
            3,
        ),
        (
            "ExplainSource",
            "ExplainSource class",
            "class ExplainSource:\n"
            "    def __call__(self):\n"
            "        return self._reader.read()\n",
            "self._reader.read",
            3,
        ),
    ],
    ids=(
        "unrelated-subject",
        "undeclared-subject",
        "out-of-scope",
        "ambiguous",
        "name-only",
    ),
)
def test_symbol_claim_requires_unique_subject_and_in_scope_evidence(
    symbol: str,
    claim_text: str,
    source_text: str,
    target: str,
    line: int,
) -> None:
    source = SourceFile(Path("explain.py"), source_text)
    payload = _payload()
    payload["symbols"] = [
        {
            "symbol": symbol,
            "claim": claim_text,
            "confidence": "likely",
            "evidence": [
                {
                    "kind": "call",
                    "target": target,
                    "start_line": line,
                    "end_line": line,
                }
            ],
        }
    ]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.symbols == ()
    assert result.incomplete
    assert result.processing_incomplete is True
    assert any(
        diagnostic.kind in _OMISSION_DIAGNOSTICS for diagnostic in result.diagnostics
    )


def test_missing_symbol_subject_is_discarded_and_marks_incomplete() -> None:
    source = SourceFile(
        Path("explain.py"),
        "class ExplainSource:\n"
        "    def __call__(self):\n"
        "        return self._reader.read()\n",
    )
    payload = _payload()
    payload["symbols"] = [
        {
            "claim": "Coordinates the selected source read.",
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
    ]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.symbols == ()
    assert result.incomplete


def test_syntax_error_omits_symbols_with_a_visible_scope_limitation() -> None:
    source = SourceFile(Path("explain.py"), "class ExplainSource:\n    if:\n")
    payload = _payload()
    payload["symbols"] = [
        {
            "symbol": "ExplainSource",
            "claim": "Coordinates selected-file work.",
            "confidence": "likely",
            "evidence": [
                {
                    "kind": "call",
                    "target": "self._reader.read",
                    "start_line": 2,
                    "end_line": 2,
                }
            ],
        }
    ]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert result.symbols == ()
    assert result.incomplete
    assert result.processing_incomplete is True
    assert any(
        diagnostic.kind is ExplanationDiagnosticKind.SYMBOL_VALIDATION_UNAVAILABLE
        for diagnostic in result.diagnostics
    )
    assert any("symbol scope validation" in item for item in result.limitations)
    assert "symbol_validation_unavailable" not in render_explanation(result)


def test_response_without_claims_or_limits_is_rejected() -> None:
    source = SourceFile(Path("app.py"), "a = 1\n")

    with pytest.raises(ProviderResponseError, match="no evidence-grounded"):
        parse_explanation(
            json.dumps(_payload()),
            source,
            model="fake-model",
            usage=TokenUsage(1, 1),
        )
