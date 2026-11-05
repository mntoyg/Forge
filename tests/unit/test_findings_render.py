"""Both renderers, asserted on the string they produce.

They are pure functions, so there is no stdout to capture and nothing to mock.
The plain renderer carries the stricter contract: it must survive a pipe, a log
file, and a CI transcript, none of which want escape codes or box drawing.
"""

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
)
from forge.presentation.findings import render_plain, render_rich

USAGE = TokenUsage(input_tokens=1234, output_tokens=567)

BOX_DRAWING = set("┏┓┗┛━┃│─┌┐└┘├┤┬┴┼╭╮╯╰")


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


def _result(*findings: Finding, history: FileHistory | None = None) -> AnalysisResult:
    return AnalysisResult(
        source_path=Path("/work/app.py"),
        findings=findings,
        model="gpt-4o-mini",
        usage=USAGE,
        incomplete=False,
        history=history,
    )


HISTORY = FileHistory(
    recent_commits=4,
    window_days=90,
    records=(
        ChangeRecord(
            line=2, commit="a1b2c3d", author="A U Thor", changed_on=date(2026, 1, 15)
        ),
    ),
)


RENDERERS = [render_plain, render_rich]
IDS = ["plain", "rich"]


# --- what both renderers must do -------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_a_clean_file_says_so_rather_than_printing_nothing(render: object) -> None:
    """Silence reads as "it crashed", not as "your code is fine"."""
    output = render(_result())  # type: ignore[operator]

    assert "no findings" in output
    assert "app.py" in output


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_every_finding_appears(render: object) -> None:
    output = render(  # type: ignore[operator]
        _result(_finding("First problem"), _finding("Second problem"))
    )

    assert "First problem" in output
    assert "Second problem" in output


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_the_model_and_cost_are_always_stated(render: object) -> None:
    output = render(_result(_finding()))  # type: ignore[operator]

    assert "gpt-4o-mini" in output
    assert "1,234" in output
    assert "567" in output


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_serious_findings_are_shown_first(render: object) -> None:
    output = render(  # type: ignore[operator]
        _result(
            _finding("Minor thing", Severity.LOW),
            _finding("Serious thing", Severity.HIGH),
        )
    )

    assert output.index("Serious thing") < output.index("Minor thing")


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_a_finding_without_a_location_still_renders(render: object) -> None:
    """Some findings belong to the file, not to a line. They are not dropped."""
    output = render(_result(_finding(line=None)))  # type: ignore[operator]

    assert "Divides without guarding zero" in output


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_confidence_is_shown(render: object) -> None:
    """The vision commits to honest output: uncertainty must be visible."""
    output = render(_result(_finding(confidence=Confidence.POSSIBLE)))  # type: ignore[operator]

    assert "possible" in output


# --- the plain renderer's stricter contract --------------------------------


@pytest.mark.unit
def test_plain_output_has_no_box_drawing() -> None:
    output = render_plain(_result(_finding(), _finding("Another")))

    assert not BOX_DRAWING & set(output)


@pytest.mark.unit
def test_plain_output_has_no_escape_codes() -> None:
    """A log file full of colour codes is a log file nobody greps."""
    output = render_plain(_result(_finding()))

    assert "\x1b[" not in output


@pytest.mark.unit
def test_plain_output_names_the_line() -> None:
    output = render_plain(_result(_finding(line=7)))

    assert "line 7" in output


@pytest.mark.unit
def test_plain_output_says_when_there_is_no_line() -> None:
    output = render_plain(_result(_finding(line=None)))

    assert "no line" in output


@pytest.mark.unit
def test_plain_output_counts_findings() -> None:
    output = render_plain(_result(_finding(), _finding("Second")))

    assert "2 findings" in output


@pytest.mark.unit
def test_a_single_finding_is_not_pluralised() -> None:
    assert "1 finding" in render_plain(_result(_finding()))
    assert "1 findings" not in render_plain(_result(_finding()))


# --- the rich renderer ------------------------------------------------------


@pytest.mark.unit
def test_rich_output_puts_the_line_number_in_the_table() -> None:
    output = render_rich(_result(_finding(line=42)))

    assert "42" in output


@pytest.mark.unit
def test_rich_output_marks_a_finding_with_no_line() -> None:
    output = render_rich(_result(_finding(line=None)))

    assert "-" in output


@pytest.mark.unit
def test_rich_output_labels_severity() -> None:
    output = render_rich(_result(_finding(severity=Severity.MEDIUM)))

    assert "MEDIUM" in output


@pytest.mark.unit
def test_long_detail_is_wrapped_not_truncated() -> None:
    """A finding a reader cannot finish reading is a finding they cannot act on."""
    long_detail = "This explanation is deliberately long. " * 20
    result = AnalysisResult(
        source_path=Path("app.py"),
        findings=(
            Finding(
                summary="Something",
                detail=long_detail,
                severity=Severity.HIGH,
                confidence=Confidence.LIKELY,
                location=Location(line=1),
            ),
        ),
        model="m",
        usage=USAGE,
        incomplete=False,
    )

    output = render_rich(result, width=60)

    assert "..." not in output
    assert output.count("deliberately") == 20


# --- untrusted content ------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_finding_text_is_not_interpreted_as_markup(render: object) -> None:
    """Model output is untrusted. Rich markup in it must not become styling."""
    result = _result(_finding("[bold red]not markup[/bold red]"))

    output = render(result)  # type: ignore[operator]

    assert "[bold red]not markup[/bold red]" in output


# --- history, when there is any ---------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_a_line_carries_what_git_knows_about_it(render: object) -> None:
    output = render(_result(_finding(line=2), history=HISTORY))  # type: ignore[operator]

    assert "2026-01-15" in output
    assert "a1b2c3d" in output


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_an_uncommitted_line_says_so_rather_than_naming_someone(
    render: object,
) -> None:
    """Attributing the developer's own unsaved work to a previous author lies."""
    output = render(_result(_finding(line=9), history=HISTORY))  # type: ignore[operator]

    assert "not committed yet" in output


@pytest.mark.unit
@pytest.mark.parametrize("render", RENDERERS, ids=IDS)
def test_how_much_the_file_has_been_moving_is_stated_with_its_window(
    render: object,
) -> None:
    """A count with no period attached is a number nobody can read."""
    output = render(_result(_finding(line=2), history=HISTORY))  # type: ignore[operator]

    assert "4 commits in the last 90 days" in output


@pytest.mark.unit
def test_one_commit_is_not_pluralised() -> None:
    history = FileHistory(recent_commits=1, window_days=90)

    output = render_plain(_result(_finding(line=2), history=history))

    assert "1 commit in the last 90 days" in output


@pytest.mark.unit
def test_no_repository_means_no_annotation_at_all() -> None:
    """Absent history is silent. An empty label would read as a fact."""
    output = render_plain(_result(_finding(line=2)))

    assert "history:" not in output
    assert "commits in the last" not in output


@pytest.mark.unit
def test_a_finding_with_no_line_gets_no_history_note() -> None:
    """There is no line to look up, so there is nothing honest to print."""
    output = render_plain(_result(_finding(line=None), history=HISTORY))

    assert "history:" not in output


@pytest.mark.unit
def test_plain_history_output_has_no_escape_codes() -> None:
    output = render_plain(_result(_finding(line=2), history=HISTORY))

    assert "\x1b[" not in output
