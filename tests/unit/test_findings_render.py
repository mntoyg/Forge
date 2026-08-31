"""Both renderers, asserted on the string they produce.

They are pure functions, so there is no stdout to capture and nothing to mock.
The plain renderer carries the stricter contract: it must survive a pipe, a log
file, and a CI transcript, none of which want escape codes or box drawing.
"""

from pathlib import Path

import pytest

from forge.domain.ai import TokenUsage
from forge.domain.source import (
    AnalysisResult,
    Confidence,
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


def _result(*findings: Finding) -> AnalysisResult:
    return AnalysisResult(
        source_path=Path("/work/app.py"),
        findings=findings,
        model="gpt-4o-mini",
        usage=USAGE,
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
