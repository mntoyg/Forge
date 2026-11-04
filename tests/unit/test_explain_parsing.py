import json
from pathlib import Path

import pytest

from forge.application.explain_parsing import parse_explanation
from forge.domain.ai import TokenUsage
from forge.domain.errors import ProviderResponseError
from forge.domain.explanation import EvidenceKind
from forge.domain.source import SourceFile


def _payload(*claims: object) -> dict[str, object]:
    return {
        "purpose": list(claims),
        "flow": [],
        "symbols": [],
        "limitations": [],
        "context_insufficient": False,
    }


def _claim(
    start: object = 1, end: object = 2, target: str = "a = 1"
) -> dict[str, object]:
    return {
        "claim": "Calculates a total.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "operation",
                "target": target,
                "start_line": start,
                "end_line": end,
            }
        ],
    }


def test_evidence_kind_remains_a_string_enum() -> None:
    assert EvidenceKind("call") is EvidenceKind.CALL
    assert isinstance(EvidenceKind.CALL, str)


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


def test_valid_one_based_range_is_preserved() -> None:
    source = SourceFile(Path("app.py"), "a = 1\nb = 2\n")

    result = parse_explanation(
        json.dumps(_payload(_claim())),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose[0].evidence[0].start_line == 1
    assert result.purpose[0].evidence[0].end_line == 2
    assert result.purpose[0].evidence[0].kind.value == "operation"
    assert result.purpose[0].evidence[0].target == "a = 1"
    assert not result.incomplete


def test_model_certain_confidence_is_capped_at_likely() -> None:
    source = SourceFile(Path("app.py"), "total = sum(values)\n")
    claim = _claim(1, 1, target="total = sum(values)")
    claim["confidence"] = "certain"

    result = parse_explanation(
        json.dumps(_payload(claim)),
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
    source = SourceFile(Path("app.py"), "value = self._reader.value\n")
    claim = {
        "claim": "The reader supplies the value.",
        "confidence": "likely",
        "evidence": [
            {
                "kind": "access",
                "target": "self._reader.value",
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
    assert any("symbol scope validation" in item for item in result.limitations)


def test_response_without_claims_or_limits_is_rejected() -> None:
    source = SourceFile(Path("app.py"), "a = 1\n")

    with pytest.raises(ProviderResponseError, match="no evidence-grounded"):
        parse_explanation(
            json.dumps(_payload()),
            source,
            model="fake-model",
            usage=TokenUsage(1, 1),
        )
