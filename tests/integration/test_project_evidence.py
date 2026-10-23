"""Project evidence discovery is bounded and excludes unsafe paths."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from forge.application.inspect import InspectProject
from forge.infrastructure import project as project_adapter
from forge.infrastructure.project import FilesystemProjectEvidenceReader
from forge.presentation.project import render_project_overview


@pytest.mark.integration
def test_reader_skips_ignored_sensitive_generated_and_symlinked_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".gitignore").write_text("ignored/\n*.tmp\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\napi_key = "not-for-output"\n',
        encoding="utf-8",
    )
    (root / ".env").write_text("FORGE_API_KEY=not-for-output", encoding="utf-8")
    (root / "ignored").mkdir()
    (root / "ignored" / "secret.py").write_text("ignored", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (root / "src" / ".gitignore").write_text("local/\n", encoding="utf-8")
    (root / "src" / "local").mkdir()
    (root / "src" / "local" / "ignored.ts").write_text("ignored", encoding="utf-8")
    (root / "asset.png").write_bytes(b"binary")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "app.js").write_text("ignored", encoding="utf-8")
    (root / "cache.tmp").write_text("ignored", encoding="utf-8")
    reader = FilesystemProjectEvidenceReader()
    evidence = reader.collect(root)
    output = render_project_overview(InspectProject(reader)(root))

    assert {item.path for item in evidence.files} == {"pyproject.toml"}
    assert "src/app.py" in evidence.file_paths
    assert not any("ignored" in path for path in evidence.file_paths)
    assert not any(path.endswith("asset.png") for path in evidence.file_paths)
    assert ".env" not in evidence.file_paths
    assert "node_modules" not in evidence.directories
    assert "not-for-output" not in output


@pytest.mark.integration
def test_reader_does_not_follow_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("secret source", encoding="utf-8")
    try:
        (root / "linked.py").symlink_to(outside)
    except OSError:
        pytest.skip("creating a symlink needs elevation or developer mode")

    evidence = FilesystemProjectEvidenceReader().collect(root)

    assert "linked.py" not in evidence.file_paths


@pytest.mark.integration
def test_reader_reports_incomplete_scan_when_entry_limit_is_reached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    for name in ("one.py", "two.py", "three.py"):
        (root / name).write_text("pass", encoding="utf-8")
    monkeypatch.setattr(project_adapter, "MAX_ENTRIES", 2)

    evidence = FilesystemProjectEvidenceReader().collect(root)

    assert not evidence.complete
    assert evidence.entries_seen == 2
    assert any("entry" in omission for omission in evidence.omissions)


@pytest.mark.integration
def test_reader_reports_metadata_omitted_at_total_byte_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]", encoding="utf-8")
    monkeypatch.setattr(project_adapter, "MAX_BYTES", 4)

    evidence = FilesystemProjectEvidenceReader().collect(root)

    assert not evidence.complete
    assert not evidence.files
    assert any("byte read limit" in omission for omission in evidence.omissions)


@pytest.mark.integration
def test_reader_reports_unreadable_metadata_as_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    metadata = root / "pyproject.toml"
    metadata.write_text("[project]", encoding="utf-8")
    monkeypatch.setattr(Path, "open", Mock(side_effect=PermissionError("blocked")))

    evidence = FilesystemProjectEvidenceReader().collect(root)

    assert not evidence.files
    assert "Could not read UTF-8 metadata: pyproject.toml" in evidence.omissions
