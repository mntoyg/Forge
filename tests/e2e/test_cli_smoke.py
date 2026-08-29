"""End-to-end smoke tests for the installed CLI.

These drive the Typer application the way a user would. They must not require
network access or an API key.
"""

import pytest
from typer.testing import CliRunner

from forge import __version__
from forge.main import app

runner = CliRunner()


@pytest.mark.e2e
def test_version_flag_reports_the_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


@pytest.mark.e2e
def test_bare_invocation_shows_help_instead_of_failing_silently() -> None:
    result = runner.invoke(app, [])

    assert "Usage" in result.stdout


@pytest.mark.e2e
def test_debug_command_is_not_implemented_yet() -> None:
    """Guards the Day 1 scope boundary.

    ``forge debug`` is the planned first capability. Until it is designed,
    reviewed, and implemented, invoking it must fail rather than half-work.
    Delete this test in the same change that introduces the real command.
    """
    result = runner.invoke(app, ["debug", "example.py"])

    assert result.exit_code != 0
