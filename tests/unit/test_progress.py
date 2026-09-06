"""The spinner shown while the provider is thinking.

Two questions, and they are separate on purpose: whether a spinner should be
drawn at all, and what it draws. The first is a decision about the terminal the
user is sitting at; the second is rendering. Testing them apart is what lets
the first one be checked without a terminal.
"""

import io
import sys
from pathlib import Path

import pytest
from rich.console import Console

from forge.cli import debug as debug_cli


class _Terminal(io.StringIO):
    """A stream that claims to be a terminal, because a test has none."""

    def isatty(self) -> bool:
        return True


# --- whether to draw one at all ---------------------------------------------


@pytest.mark.unit
def test_a_terminal_gets_a_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", _Terminal())

    assert debug_cli._progress_console(plain=False) is not None


@pytest.mark.unit
def test_a_pipe_gets_no_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Escape codes in a log file are noise nobody asked for."""
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    assert debug_cli._progress_console(plain=False) is None


@pytest.mark.unit
def test_plain_output_gets_no_spinner(monkeypatch: pytest.MonkeyPatch) -> None:
    """--plain means plain, including the parts that are not the result."""
    monkeypatch.setattr(sys, "stderr", _Terminal())

    assert debug_cli._progress_console(plain=True) is None


@pytest.mark.unit
def test_the_spinner_is_drawn_on_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    """A piped stdout carries results only - the rule the errors already follow."""
    monkeypatch.setattr(sys, "stderr", _Terminal())

    console = debug_cli._progress_console(plain=False)

    assert console is not None
    assert console.stderr


# --- what it draws ----------------------------------------------------------


@pytest.mark.unit
def test_the_spinner_names_the_file_being_analysed() -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=80)

    with debug_cli._waiting(console, Path("/work/app.py")):
        pass

    assert "app.py" in buffer.getvalue()


@pytest.mark.unit
def test_no_console_draws_nothing_and_still_runs_the_body(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The absence of a spinner must never be the absence of the analysis."""
    ran = False

    with debug_cli._waiting(None, Path("app.py")):
        ran = True

    captured = capsys.readouterr()
    assert ran
    assert captured.out == ""
    assert captured.err == ""
