"""Project overview claims stay tied to the evidence supplied to the use case."""

from pathlib import Path

import pytest

from forge.application.inspect import InspectProject
from forge.domain.errors import SourceNotFoundError, SourceUnreadableError
from forge.domain.project import ProjectEvidence, ProjectFile
from forge.presentation.project import render_project_overview


class _Evidence:
    def __init__(self, evidence: ProjectEvidence) -> None:
        self.evidence = evidence

    def collect(self, root: Path) -> ProjectEvidence:
        return self.evidence


@pytest.mark.unit
def test_inspect_reports_facts_with_paths_and_only_existing_checks(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    evidence = ProjectEvidence(
        root=root,
        files=(
            ProjectFile(
                "pyproject.toml",
                '[project]\nrequires-python = ">=3.13"\n[tool.pytest.ini_options]\n',
            ),
            ProjectFile("package.json", '{"scripts":{"test":"node test.js"}}'),
            ProjectFile("Makefile", "test:\n\t@echo test\n"),
        ),
        file_paths=(
            "AGENTS.md",
            ".forge/context/status.md",
            "src/main.py",
            "web/app.tsx",
            "pyproject.toml",
            "uv.lock",
            "package.json",
            "Makefile",
        ),
        directories=("src", "web"),
        entries_seen=7,
        complete=True,
    )

    overview = InspectProject(_Evidence(evidence))(root)

    assert overview.guidance == (".forge/context/status.md", "AGENTS.md")
    assert [(fact.name, fact.paths) for fact in overview.languages] == [
        ("Python", ("src/main.py",)),
        ("TypeScript", ("web/app.tsx",)),
    ]
    assert any(fact.name == "pytest configuration" for fact in overview.tooling)
    assert {fact.name for fact in overview.checks} == {
        "npm run test",
        "make test",
        "uv run pytest",
    }
    assert overview.directories == ("src", "web")


@pytest.mark.unit
def test_inspect_explains_when_no_supported_metadata_is_present(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    evidence = ProjectEvidence(root, (), ("notes.txt",), (), 1, True)

    overview = InspectProject(_Evidence(evidence))(root)

    assert any(
        omission.startswith("No supported project metadata file was found;")
        for omission in overview.omissions
    )
    assert not overview.languages


@pytest.mark.unit
def test_inspect_refuses_a_missing_or_non_directory_root(tmp_path: Path) -> None:
    inspect = InspectProject(_Evidence(ProjectEvidence(tmp_path, (), (), (), 0, True)))

    with pytest.raises(SourceNotFoundError):
        inspect(tmp_path / "missing")
    (tmp_path / "file.txt").write_text("not a directory", encoding="utf-8")
    with pytest.raises(SourceUnreadableError):
        inspect(tmp_path / "file.txt")


@pytest.mark.unit
def test_malformed_project_metadata_is_reported_without_echoing_its_content(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    evidence = ProjectEvidence(
        root,
        (ProjectFile("pyproject.toml", 'token = "do-not-print"\ninvalid'),),
        ("pyproject.toml",),
        ("pyproject.toml",),
        1,
        True,
    )

    overview = InspectProject(_Evidence(evidence))(root)

    assert any(fact.name == "Malformed pyproject.toml" for fact in overview.tooling)
    assert "do-not-print" not in render_project_overview(overview)
