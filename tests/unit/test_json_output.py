"""JSON serializers expose stable, safe result data without external effects."""

import json
from datetime import date
from pathlib import Path

import pytest

from forge.domain.ai import TokenUsage
from forge.domain.project import (
    ProjectFact,
    ProjectOmission,
    ProjectOmissionCode,
    ProjectOverview,
)
from forge.domain.source import (
    AnalysisResult,
    ChangeRecord,
    Confidence,
    FileHistory,
    Finding,
    Location,
    Severity,
)
from forge.presentation.json_output import (
    DebugJsonInput,
    DebugMode,
    serialize_debug_json,
    serialize_inspect_json,
)


def _debug(
    *, incomplete: bool = False, history: FileHistory | None = None
) -> AnalysisResult:
    return AnalysisResult(
        source_path=Path("C:/private/workspace/src/app.py"),
        findings=(
            Finding(
                "Possible unchecked value",
                "The value is used before a null check.",
                Severity.MEDIUM,
                Confidence.LIKELY,
                Location(12),
            ),
            Finding(
                "File-level concern",
                "No single line can represent this claim.",
                Severity.LOW,
                Confidence.POSSIBLE,
            ),
        ),
        model="configured-model",
        usage=TokenUsage(100, 20),
        incomplete=incomplete,
        history=history,
    )


@pytest.mark.unit
@pytest.mark.parametrize("mode", [DebugMode.FILE, DebugMode.DIFF])
def test_debug_json_is_one_object_with_safe_paths_optional_fields_and_no_raw_text(
    mode: DebugMode,
) -> None:
    history = FileHistory(
        3,
        30,
        (ChangeRecord(12, "abc123", "A Developer", date(2026, 1, 2)),),
    )

    encoded = serialize_debug_json(
        DebugJsonInput(_debug(history=history), "src/app.py", mode)
    )
    payload = json.loads(encoded)

    assert set(payload) == {
        "schema_version",
        "command",
        "status",
        "result",
        "completeness",
    }
    assert payload["schema_version"] == 1
    assert payload["command"] == "debug"
    assert payload["status"] == "success"
    assert payload["result"]["path"] == "src/app.py"
    assert payload["result"]["mode"] == mode.value
    assert payload["result"]["findings"][0]["location"] == {"line": 12}
    assert payload["result"]["findings"][1]["location"] is None
    assert payload["result"]["history"]["records"][0]["changed_on"] == "2026-01-02"
    assert payload["completeness"] == {
        "status": "complete",
        "warnings": [],
        "omissions": [],
    }
    assert "C:/private/workspace" not in encoded
    assert "raw provider response" not in encoded


@pytest.mark.unit
def test_debug_json_marks_known_size_warning_and_parser_omission_partial() -> None:
    payload = json.loads(
        serialize_debug_json(
            DebugJsonInput(
                _debug(incomplete=True),
                "src/app.py",
                DebugMode.FILE,
                whole_file_size_warning=True,
            )
        )
    )

    assert payload["completeness"] == {
        "status": "partial",
        "warnings": [{"code": "whole_file_size_limit"}],
        "omissions": [{"code": "provider_findings_discarded"}],
    }


@pytest.mark.unit
def test_debug_json_omits_unavailable_history_as_null() -> None:
    payload = json.loads(
        serialize_debug_json(DebugJsonInput(_debug(), "src/app.py", DebugMode.FILE))
    )

    assert payload["result"]["history"] is None


@pytest.mark.unit
def test_debug_json_rejects_absolute_or_parent_paths() -> None:
    for path in ("C:/private/app.py", "../outside.py"):
        with pytest.raises(ValueError, match="workspace-relative"):
            serialize_debug_json(DebugJsonInput(_debug(), path, DebugMode.FILE))


@pytest.mark.unit
@pytest.mark.parametrize(
    "scan_complete, expected", [(True, "complete"), (False, "partial")]
)
def test_inspect_json_uses_typed_omissions_and_scan_completeness(
    tmp_path: Path, scan_complete: bool, expected: str
) -> None:
    overview = ProjectOverview(
        root=tmp_path / "private-project",
        guidance=("AGENTS.md",),
        languages=(ProjectFact("Python", ("src/app.py",)),),
        tooling=(),
        checks=(),
        directories=("src",),
        omissions=("Do not serialize this prose or any root path.",),
        scan_complete=scan_complete,
        structured_omissions=(
            ProjectOmission(ProjectOmissionCode.ENTRY_LIMIT),
            ProjectOmission(ProjectOmissionCode.METADATA_BYTE_LIMIT, "pyproject.toml"),
        ),
    )

    encoded = serialize_inspect_json(overview)
    payload = json.loads(encoded)

    assert payload["completeness"]["status"] == expected
    assert payload["completeness"]["omissions"] == [
        {"code": "entry_limit"},
        {"code": "metadata_byte_limit", "path": "pyproject.toml"},
    ]
    assert payload["result"]["root"] == "."
    assert payload["result"]["languages"] == [
        {"name": "Python", "evidence": ["src/app.py"]}
    ]
    assert "private-project" not in encoded
    assert "Do not serialize this prose" not in encoded


@pytest.mark.unit
def test_inspect_json_rejects_unsafe_fact_paths(tmp_path: Path) -> None:
    overview = ProjectOverview(
        root=tmp_path,
        guidance=(),
        languages=(ProjectFact("Python", ("../outside.py",)),),
        tooling=(),
        checks=(),
        directories=(),
        omissions=(),
        scan_complete=True,
    )

    with pytest.raises(ValueError, match="workspace-relative"):
        serialize_inspect_json(overview)
