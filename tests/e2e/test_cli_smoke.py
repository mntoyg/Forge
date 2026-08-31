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
def test_the_debug_command_is_registered() -> None:
    """The real command replaced the Day 1 placeholder that guarded this name.

    Behaviour is covered in ``test_debug_command.py``; this only asserts the
    composition root wired it in, which no other test can see.
    """
    result = runner.invoke(app, ["--help"])

    assert "debug" in result.stdout


@pytest.mark.e2e
def test_version_works_without_any_configuration() -> None:
    """Configuration is loaded per command, not at import.

    If that ever changes, ``--version`` starts demanding an API key, and the
    first thing a new user runs stops working.
    """
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "FORGE_API_KEY" not in result.output
