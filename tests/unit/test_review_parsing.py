"""Model paths and lines are accepted only when tied to the local snapshot."""

import json
from pathlib import Path
from typing import Any

import pytest

from forge.application.parsing import parse_review_findings
from forge.domain.errors import ProviderResponseError
from forge.domain.review import ChangeKind, ChangeSet, ReviewFile
from forge.domain.source import Confidence, Location, Severity

CHANGES = ChangeSet(
    root=Path(),
    files=(
        ReviewFile(
            path=Path("src/app.py"),
            content="one = 1\ntwo = 0\nthree = 3\n",
            changed_lines=frozenset({2}),
            kind=ChangeKind.MODIFIED,
        ),
    ),
    omissions=(),
)


def _finding(**overrides: Any) -> dict[str, object]:
    finding: dict[str, object] = {
        "path": "src/app.py",
        "line": 2,
        "summary": "Division by zero",
        "detail": "The changed divisor can be zero.",
        "severity": "high",
        "confidence": "certain",
    }
    finding.update(overrides)
    return finding


def _reply(*findings: object) -> str:
    return json.dumps({"findings": list(findings)})


@pytest.mark.unit
def test_valid_review_finding_uses_snapshot_evidence() -> None:
    parsed = parse_review_findings(_reply(_finding()), CHANGES)

    assert parsed.complete is True
    assert len(parsed.findings) == 1
    finding = parsed.findings[0]
    assert finding.path == Path("src/app.py")
    assert finding.location == Location(line=2)
    assert finding.evidence == "two = 0"
    assert finding.severity is Severity.HIGH
    assert finding.confidence is Confidence.CERTAIN


@pytest.mark.unit
@pytest.mark.parametrize(
    "broken",
    [
        {"path": "unknown.py"},
        {"line": 1},
        {"line": 0},
        {"line": 99},
        {"line": True},
        {"path": "../src/app.py"},
        {"path": "src\\app.py"},
        {"summary": "", "detail": "missing summary"},
    ],
)
def test_invalid_paths_lines_and_fields_are_dropped_incompletely(
    broken: dict[str, object],
) -> None:
    parsed = parse_review_findings(_reply(_finding(), _finding(**broken)), CHANGES)

    assert len(parsed.findings) == 1
    assert parsed.complete is False


@pytest.mark.unit
def test_an_empty_findings_list_is_a_complete_result() -> None:
    parsed = parse_review_findings(_reply(), CHANGES)

    assert parsed.findings == ()
    assert parsed.complete is True


@pytest.mark.unit
def test_unparseable_review_reply_is_not_echoed_in_an_error() -> None:
    untrusted_reply = "provider echoed this credential-value-should-not-print"

    with pytest.raises(ProviderResponseError) as caught:
        parse_review_findings(untrusted_reply, CHANGES)

    assert untrusted_reply not in str(caught.value)
