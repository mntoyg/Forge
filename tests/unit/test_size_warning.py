"""The caveat printed when a result may only cover the start of a file.

ADR-0011. The measurement behind it: one unguarded division, appended to the
end of real files, is reported at 3,927 input tokens and missed at 10,225 -
while the same defect at line 6 of that same 10,225-token file is found
immediately. The model reads the beginning of a long file and stops, and "no
findings" is what that silence looks like.
"""

from pathlib import Path

import pytest

from forge.cli import debug as debug_cli
from forge.cli.exit_codes import ExitCode
from forge.domain.ai import TokenUsage
from forge.domain.source import (
    AnalysisResult,
    Confidence,
    Finding,
    Location,
    Severity,
)

FINDING = Finding(
    summary="Divides without guarding zero",
    detail="An empty list raises ZeroDivisionError.",
    severity=Severity.HIGH,
    confidence=Confidence.CERTAIN,
    location=Location(line=2),
)


def _result(input_tokens: int, *findings: Finding) -> AnalysisResult:
    return AnalysisResult(
        source_path=Path("/work/app.py"),
        findings=findings,
        model="gpt-4o-mini",
        usage=TokenUsage(input_tokens=input_tokens, output_tokens=8),
        incomplete=False,
    )


# --- when it is said --------------------------------------------------------


@pytest.mark.unit
def test_a_short_file_gets_no_caveat() -> None:
    """Most files are short. A caveat on all of them would be read by nobody."""
    assert debug_cli._size_warning(_result(3_927), changes_only=False) is None


@pytest.mark.unit
def test_the_threshold_itself_is_still_trusted() -> None:
    """It is the last size seen to work, so it is inside the promise."""
    assert (
        debug_cli._size_warning(
            _result(debug_cli.RELIABLE_INPUT_TOKENS), changes_only=False
        )
        is None
    )


@pytest.mark.unit
def test_a_long_file_is_flagged() -> None:
    assert debug_cli._size_warning(_result(10_225), changes_only=False) is not None


@pytest.mark.unit
def test_findings_do_not_excuse_the_caveat() -> None:
    """The 1,922-line run returned two findings and still missed the injected one.

    A partial review is partial whether or not it found something on the way.
    """
    assert (
        debug_cli._size_warning(_result(23_359, FINDING), changes_only=False)
        is not None
    )


# --- what it says -----------------------------------------------------------


@pytest.mark.unit
def test_the_caveat_names_the_file_and_what_it_cost() -> None:
    """A number the reader can check beats an adjective they cannot."""
    warning = debug_cli._size_warning(_result(44_295), changes_only=False)

    assert warning is not None
    assert "app.py" in warning
    assert "44,295" in warning


@pytest.mark.unit
def test_the_caveat_says_which_part_of_the_file_it_doubts() -> None:
    """It is attention running out, not a size limit - the end is what is lost."""
    warning = debug_cli._size_warning(_result(44_295), changes_only=False)

    assert warning is not None
    assert "end of a file" in warning


# --- where it goes ----------------------------------------------------------


@pytest.mark.unit
def test_the_caveat_goes_to_stderr_and_leaves_stdout_alone(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A piped stdout carries results only - the rule the errors already follow."""

    def analyze(path: Path, *, changes_only: bool = False) -> AnalysisResult:
        return _result(44_295, FINDING)

    code = debug_cli.debug(analyze, Path("app.py"), plain=True)

    captured = capsys.readouterr()
    assert code is ExitCode.OK
    assert "forge:" in captured.err
    assert "44,295" in captured.err
    assert "forge:" not in captured.out
    assert "Divides without guarding zero" in captured.out


@pytest.mark.unit
def test_a_short_run_says_nothing_extra(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def analyze(path: Path, *, changes_only: bool = False) -> AnalysisResult:
        return _result(500, FINDING)

    debug_cli.debug(analyze, Path("app.py"), plain=True)

    assert capsys.readouterr().err == ""


# --- a change review is a different question --------------------------------


@pytest.mark.unit
def test_a_change_review_is_not_caveated() -> None:
    """Marking the changed lines carries attention to them wherever they sit.

    The same defect a whole-file run misses at the end of a 3,807-line file is
    found there by --diff, at 44,409 input tokens. ADR-0012.
    """
    assert debug_cli._size_warning(_result(44_409), changes_only=True) is None


@pytest.mark.unit
def test_a_change_review_says_nothing_even_when_it_finds_something() -> None:
    warning = debug_cli._size_warning(_result(44_409, FINDING), changes_only=True)

    assert warning is None


@pytest.mark.unit
def test_the_diff_flag_silences_the_caveat_end_to_end(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A caveat that fires where the evidence says it should not teaches people
    to ignore it where it matters."""

    def analyze(path: Path, *, changes_only: bool = False) -> AnalysisResult:
        return _result(44_295, FINDING)

    debug_cli.debug(analyze, Path("app.py"), plain=True, changes_only=True)

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Divides without guarding zero" in captured.out
