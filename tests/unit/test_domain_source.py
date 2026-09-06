"""The source and finding value objects enforce their own invariants."""

from datetime import date
from pathlib import Path

import pytest

from forge.domain.ai import TokenUsage
from forge.domain.source import (
    AnalysisResult,
    ChangeRecord,
    Confidence,
    FileHistory,
    Finding,
    Location,
    Severity,
    SourceFile,
)

USAGE = TokenUsage(input_tokens=10, output_tokens=5)


def _finding(
    summary: str = "Divides without guarding zero",
    severity: Severity = Severity.HIGH,
    confidence: Confidence = Confidence.CERTAIN,
    line: int | None = 2,
) -> Finding:
    return Finding(
        summary=summary,
        detail="An empty list raises ZeroDivisionError.",
        severity=severity,
        confidence=confidence,
        location=Location(line=line) if line is not None else None,
    )


# --- Location --------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("line", [0, -1, -99])
def test_a_location_cannot_point_before_the_first_line(line: int) -> None:
    with pytest.raises(ValueError, match="Line numbers start at 1"):
        Location(line=line)


@pytest.mark.unit
def test_line_one_is_a_valid_location() -> None:
    assert Location(line=1).line == 1


# --- Finding ---------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("summary", ["", "   ", "\n"])
def test_a_finding_must_name_the_defect(summary: str) -> None:
    with pytest.raises(ValueError, match="must have a summary"):
        Finding(
            summary=summary,
            detail="detail",
            severity=Severity.LOW,
            confidence=Confidence.POSSIBLE,
        )


@pytest.mark.unit
def test_a_finding_must_explain_itself() -> None:
    """A summary with no explanation is an accusation, not a review."""
    with pytest.raises(ValueError, match="must explain itself"):
        Finding(
            summary="Something is wrong",
            detail="  ",
            severity=Severity.LOW,
            confidence=Confidence.POSSIBLE,
        )


@pytest.mark.unit
def test_a_finding_may_have_no_location() -> None:
    """Some real findings belong to the whole file, not to one line."""
    finding = Finding(
        summary="No error handling anywhere in this module",
        detail="Every call can raise, and none is guarded.",
        severity=Severity.MEDIUM,
        confidence=Confidence.LIKELY,
    )

    assert finding.location is None


@pytest.mark.unit
def test_severity_and_confidence_use_different_words() -> None:
    """Two scales sharing high/medium/low would be misread constantly."""
    assert not set(Severity) & {c.value for c in Confidence}


# --- SourceFile ------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("content", ["", "   ", "\n\n\t"])
def test_an_empty_file_is_not_worth_analysing(content: str) -> None:
    with pytest.raises(ValueError, match="nothing to analyse"):
        SourceFile(path=Path("empty.py"), content=content)


@pytest.mark.unit
def test_line_count_matches_the_content() -> None:
    source = SourceFile(path=Path("a.py"), content="one\ntwo\nthree\n")

    assert source.line_count == 3


@pytest.mark.unit
def test_content_is_numbered_for_the_prompt() -> None:
    """The model cannot cite a line it was never shown."""
    source = SourceFile(path=Path("a.py"), content="first\nsecond\n")

    numbered = source.numbered()

    assert "   1 | first" in numbered
    assert "   2 | second" in numbered


@pytest.mark.unit
def test_numbering_covers_every_line_exactly_once() -> None:
    source = SourceFile(path=Path("a.py"), content="\n".join(str(i) for i in range(20)))

    assert len(source.numbered().splitlines()) == source.line_count


# --- AnalysisResult --------------------------------------------------------


@pytest.mark.unit
def test_a_result_with_no_findings_reports_so() -> None:
    result = AnalysisResult(
        source_path=Path("a.py"), findings=(), model="m", usage=USAGE
    )

    assert not result.has_findings
    assert result.by_severity() == ()


@pytest.mark.unit
def test_findings_are_ordered_most_serious_first() -> None:
    """Whatever appears first is what a hurried reader acts on."""
    result = AnalysisResult(
        source_path=Path("a.py"),
        findings=(
            _finding("low one", Severity.LOW),
            _finding("high one", Severity.HIGH),
            _finding("medium one", Severity.MEDIUM),
        ),
        model="m",
        usage=USAGE,
    )

    assert [f.summary for f in result.by_severity()] == [
        "high one",
        "medium one",
        "low one",
    ]


@pytest.mark.unit
def test_equally_serious_findings_are_ordered_most_confident_first() -> None:
    result = AnalysisResult(
        source_path=Path("a.py"),
        findings=(
            _finding("possible", Severity.HIGH, Confidence.POSSIBLE),
            _finding("certain", Severity.HIGH, Confidence.CERTAIN),
            _finding("likely", Severity.HIGH, Confidence.LIKELY),
        ),
        model="m",
        usage=USAGE,
    )

    assert [f.summary for f in result.by_severity()] == [
        "certain",
        "likely",
        "possible",
    ]


@pytest.mark.unit
def test_ordering_does_not_drop_or_duplicate_findings() -> None:
    findings = tuple(
        _finding(f"finding {i}", Severity.MEDIUM, line=i) for i in range(1, 6)
    )
    result = AnalysisResult(
        source_path=Path("a.py"), findings=findings, model="m", usage=USAGE
    )

    assert sorted(f.summary for f in result.by_severity()) == sorted(
        f.summary for f in findings
    )


@pytest.mark.unit
def test_a_result_carries_the_model_and_what_it_cost() -> None:
    """The user paid for both, and both are the first questions asked."""
    result = AnalysisResult(
        source_path=Path("a.py"),
        findings=(),
        model="gpt-4o-mini-2024-07-18",
        usage=TokenUsage(input_tokens=1200, output_tokens=300),
    )

    assert result.model == "gpt-4o-mini-2024-07-18"
    assert result.usage.total_tokens == 1500


# --- history ----------------------------------------------------------------


@pytest.mark.unit
def test_a_change_record_must_name_the_commit_it_came_from() -> None:
    """A record with no commit is a claim, and claims are what Finding is for."""
    with pytest.raises(ValueError, match="commit"):
        ChangeRecord(
            line=3, commit="   ", author="A U Thor", changed_on=date(2026, 1, 15)
        )


@pytest.mark.unit
def test_a_change_record_must_point_at_a_real_line() -> None:
    with pytest.raises(ValueError, match="Line numbers start at 1"):
        ChangeRecord(
            line=0, commit="a1b2c3d", author="A U Thor", changed_on=date(2026, 1, 15)
        )


@pytest.mark.unit
def test_history_finds_the_record_for_a_line() -> None:
    history = FileHistory(
        recent_commits=4,
        window_days=90,
        records=(
            ChangeRecord(
                line=2,
                commit="a1b2c3d",
                author="A U Thor",
                changed_on=date(2026, 1, 15),
            ),
        ),
    )

    record = history.at(2)

    assert record is not None
    assert record.commit == "a1b2c3d"


@pytest.mark.unit
def test_a_line_with_no_record_is_an_answer_not_a_failure() -> None:
    """That is what an uncommitted line looks like, and it is normal."""
    history = FileHistory(recent_commits=1, window_days=90)

    assert history.at(7) is None


@pytest.mark.unit
def test_a_window_must_cover_at_least_a_day() -> None:
    with pytest.raises(ValueError, match="at least a day"):
        FileHistory(recent_commits=0, window_days=0)


@pytest.mark.unit
def test_a_commit_count_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        FileHistory(recent_commits=-1, window_days=90)


@pytest.mark.unit
def test_a_result_with_no_history_is_still_a_complete_result() -> None:
    """Outside a repository there is nothing to say, and that is not a failure."""
    result = AnalysisResult(
        source_path=Path("a.py"), findings=(), model="m", usage=USAGE
    )

    assert result.history is None
