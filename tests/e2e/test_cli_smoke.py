"""End-to-end smoke tests for the installed CLI.

These drive the Typer application the way a user would. They must not require
network access or an API key.
"""

import json
from pathlib import Path

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
def test_the_inspect_command_is_registered() -> None:
    result = runner.invoke(app, ["--help"])

    assert "inspect" in result.stdout


@pytest.mark.e2e
def test_inspect_reports_local_project_evidence_without_provider_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "AGENTS.md").write_text("untrusted guidance", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n", encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("pass", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["inspect"])

    assert result.exit_code == 0
    assert result.stdout.startswith("Project overview:")
    assert not result.stdout.lstrip().startswith("{")
    assert "AGENTS.md" in result.stdout
    assert "Python" in result.stdout
    assert "pyproject.toml" in result.stdout
    assert "untrusted guidance" not in result.stdout


@pytest.mark.e2e
@pytest.mark.parametrize("color", [False, True], ids=["pipe", "tty"])
def test_inspect_json_writes_one_object_for_the_selected_directory(
    tmp_path: Path, color: bool
) -> None:
    project = tmp_path / "nested" / "selected-project"
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n", encoding="utf-8"
    )
    (project / "app.py").write_text("pass\n", encoding="utf-8")

    result = runner.invoke(
        app, ["inspect", str(project), "--format", "json"], color=color
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "inspect"
    assert payload["result"]["root"] == "selected-project"
    assert str(project) not in result.stdout
    assert result.stdout.endswith("\n")
    assert result.stdout.count("\n") == 1
    assert "\x1b[" not in result.stdout
    assert "Project overview:" not in result.stdout
    assert result.stderr == ""


@pytest.mark.e2e
def test_inspect_reports_a_clear_error_for_a_missing_directory(
    tmp_path: Path,
) -> None:
    result = runner.invoke(app, ["inspect", str(tmp_path / "missing")])

    assert result.exit_code == 2
    assert "No such directory" in result.stderr


@pytest.mark.e2e
def test_version_works_without_any_configuration() -> None:
    """Configuration is loaded per command, not at import.

    If that ever changes, ``--version`` starts demanding an API key, and the
    first thing a new user runs stops working.
    """
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "FORGE_API_KEY" not in result.output
