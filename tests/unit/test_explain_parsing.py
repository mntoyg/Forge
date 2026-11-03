import json
from pathlib import Path

import pytest

from forge.application.explain_parsing import parse_explanation
from forge.domain.ai import TokenUsage
from forge.domain.errors import ProviderResponseError
from forge.domain.source import SourceFile


def _payload(*claims: object) -> dict[str, object]:
    return {
        "purpose": list(claims),
        "flow": [],
        "symbols": [],
        "limitations": [],
        "context_insufficient": False,
    }


def _claim(start: object = 1, end: object = 2) -> dict[str, object]:
    return {
        "claim": "Calculates a total.",
        "confidence": "likely",
        "evidence": [{"start_line": start, "end_line": end}],
    }


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
    assert not result.incomplete


def test_model_certain_confidence_is_capped_at_likely() -> None:
    source = SourceFile(Path("app.py"), "total = sum(values)\n")
    claim = _claim(1, 1)
    claim["confidence"] = "certain"

    result = parse_explanation(
        json.dumps(_payload(claim)),
        source,
        model="fake-model",
        usage=TokenUsage(1, 1),
    )

    assert result.purpose[0].confidence.value == "likely"


def test_symbol_that_only_repeats_its_name_is_discarded() -> None:
    source = SourceFile(
        Path("app.py"), "class ExplainSource:\n    def __call__(self):\n        pass\n"
    )
    payload = _payload()
    payload["symbols"] = [
        {
            "claim": "ExplainSource class",
            "confidence": "certain",
            "evidence": [{"start_line": 1, "end_line": 1}],
        },
        {
            "claim": "Coordinates the source read and provider request",
            "confidence": "likely",
            "evidence": [{"start_line": 2, "end_line": 3}],
        },
    ]

    result = parse_explanation(
        json.dumps(payload), source, model="fake-model", usage=TokenUsage(1, 1)
    )

    assert len(result.symbols) == 1
    assert "Coordinates" in result.symbols[0].text
    assert result.incomplete


def test_response_without_claims_or_limits_is_rejected() -> None:
    source = SourceFile(Path("app.py"), "a = 1\n")

    with pytest.raises(ProviderResponseError, match="no evidence-grounded"):
        parse_explanation(
            json.dumps(_payload()),
            source,
            model="fake-model",
            usage=TokenUsage(1, 1),
        )
