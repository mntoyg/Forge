"""JSON serializers expose stable, safe result data without external effects."""

import json
from datetime import date
from pathlib import Path

import pytest

from forge.domain.ai import TokenUsage
from forge.domain.explanation import (
    EvidenceAnchor,
    EvidenceKind,
    ExplanationClaim,
    ExplanationDiagnostic,
    ExplanationDiagnosticKind,
    ExplanationResult,
    ExplanationSection,
)
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
    SourceFile,
)
from forge.presentation.json_output import (
    DebugJsonInput,
    DebugMode,
    serialize_debug_json,
    serialize_explanation_json,
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
@pytest.mark.parametrize(
    "path",
    [
        "C:/private/app.py",
        "C:folder\\file.py",
        "../outside.py",
        "\\\\server\\share\\file.py",
    ],
)
def test_debug_json_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError, match="workspace-relative"):
        serialize_debug_json(DebugJsonInput(_debug(), path, DebugMode.FILE))


@pytest.mark.unit
@pytest.mark.parametrize(
    "scan_complete, expected", [(True, "complete"), (False, "partial")]
)
def test_inspect_json_uses_typed_omissions_and_scan_completeness(
    tmp_path: Path, scan_complete: bool, expected: str
) -> None:
    selected_root = tmp_path / "workspace" / "selected-project"
    overview = ProjectOverview(
        root=selected_root,
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
    assert payload["result"]["root"] == "selected-project"
    assert payload["result"]["languages"] == [
        {"name": "Python", "evidence": ["src/app.py"]}
    ]
    assert str(selected_root) not in encoded
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


@pytest.mark.unit
def test_explain_json_serializes_validated_claims_and_complete_envelope() -> None:
    sensitive_marker = "SENTINEL_SECRET_DO_NOT_EMIT"
    claim = ExplanationClaim(
        "Coordinates the operation.",
        Confidence.LIKELY,
        (EvidenceAnchor(EvidenceKind.CALL, "provider.complete", 4, 5),),
    )
    symbol = ExplanationClaim(
        "Validates the returned explanation.",
        Confidence.POSSIBLE,
        (EvidenceAnchor(EvidenceKind.RETURN_VALUE, "parse_result", 8, 9),),
        symbol="ExplainSource",
    )
    result = ExplanationResult(
        source=SourceFile(Path("private/source.py"), sensitive_marker),
        purpose=(claim,),
        flow=(claim,),
        symbols=(symbol,),
        limitations=("The explanation may omit behavior outside this file.",),
        context_insufficient=False,
        incomplete=False,
        model="configured-model",
        usage=TokenUsage(120, 30),
        diagnostics=(
            ExplanationDiagnostic(
                ExplanationSection.FLOW, ExplanationDiagnosticKind.SECTION_EMPTY
            ),
        ),
        processing_incomplete=False,
    )

    encoded = serialize_explanation_json(result, "src/explain.py")
    payload = json.loads(encoded)

    assert payload["schema_version"] == 1
    assert payload["command"] == "explain"
    assert payload["status"] == "success"
    assert payload["result"]["path"] == "src/explain.py"
    assert payload["result"]["purpose"][0]["evidence"] == [
        {
            "kind": "call",
            "target": "provider.complete",
            "start_line": 4,
            "end_line": 5,
        }
    ]
    assert payload["result"]["important_symbols"][0]["symbol"] == "ExplainSource"
    assert payload["result"]["limitations"] == [
        "The explanation may omit behavior outside this file."
    ]
    assert payload["result"]["usage"] == {"input_tokens": 120, "output_tokens": 30}
    assert payload["result"]["diagnostics"] == [
        {"section": "flow", "kind": "section_empty", "count": 1}
    ]
    assert payload["completeness"] == {
        "status": "complete",
        "warnings": [{"code": "limitation_present", "section": None}],
        "omissions": [],
    }
    assert sensitive_marker not in encoded
    assert "private/source.py" not in encoded


@pytest.mark.unit
@pytest.mark.parametrize(
    ("processing_incomplete", "diagnostics", "expected_status", "expected_omissions"),
    [
        (
            True,
            (
                ExplanationDiagnostic(
                    ExplanationSection.PURPOSE,
                    ExplanationDiagnosticKind.CLAIM_MALFORMED,
                    2,
                ),
            ),
            "partial",
            [{"code": "claim_unavailable", "section": "purpose", "count": 2}],
        ),
        (False, (), "complete", []),
        (
            None,
            (
                ExplanationDiagnostic(
                    None, ExplanationDiagnosticKind.SOURCE_VALIDATION_UNAVAILABLE
                ),
            ),
            "unknown",
            [],
        ),
    ],
)
def test_explain_json_maps_processing_completeness(
    processing_incomplete: bool | None,
    diagnostics: tuple[ExplanationDiagnostic, ...],
    expected_status: str,
    expected_omissions: list[dict[str, object]],
) -> None:
    result = ExplanationResult(
        source=SourceFile(Path("source.py"), "source"),
        purpose=(),
        flow=(),
        symbols=(),
        limitations=(),
        context_insufficient=False,
        incomplete=processing_incomplete is True,
        model="configured-model",
        usage=TokenUsage(1, 1),
        diagnostics=diagnostics,
        processing_incomplete=processing_incomplete,
    )

    payload = json.loads(serialize_explanation_json(result, "source.py"))

    assert payload["completeness"]["status"] == expected_status
    assert payload["completeness"]["omissions"] == expected_omissions


@pytest.mark.unit
def test_explain_json_rejects_important_symbol_without_a_subject() -> None:
    result = ExplanationResult(
        source=SourceFile(Path("source.py"), "source"),
        purpose=(),
        flow=(),
        symbols=(
            ExplanationClaim(
                "A role description.",
                Confidence.LIKELY,
                (EvidenceAnchor(EvidenceKind.OPERATION, "call", 1, 1),),
            ),
        ),
        limitations=(),
        context_insufficient=False,
        incomplete=False,
        model="configured-model",
        usage=TokenUsage(1, 1),
        processing_incomplete=False,
    )

    with pytest.raises(ValueError, match="must identify its symbol"):
        serialize_explanation_json(result, "source.py")


@pytest.mark.unit
def test_explain_json_aggregates_omissions_and_sorts_stable_metadata() -> None:
    result = ExplanationResult(
        source=SourceFile(Path("source.py"), "source"),
        purpose=(),
        flow=(),
        symbols=(),
        limitations=(),
        context_insufficient=False,
        incomplete=True,
        model="configured-model",
        usage=TokenUsage(1, 1),
        diagnostics=(
            ExplanationDiagnostic(
                ExplanationSection.FLOW, ExplanationDiagnosticKind.EVIDENCE_OUT_OF_SCOPE
            ),
            ExplanationDiagnostic(
                ExplanationSection.FLOW,
                ExplanationDiagnosticKind.EVIDENCE_TARGET_NOT_FOUND,
                2,
            ),
            ExplanationDiagnostic(
                ExplanationSection.PURPOSE, ExplanationDiagnosticKind.CLAIM_MALFORMED
            ),
            ExplanationDiagnostic(
                ExplanationSection.SYMBOLS,
                ExplanationDiagnosticKind.CONFIDENCE_UNRECOGNIZED,
            ),
            ExplanationDiagnostic(None, ExplanationDiagnosticKind.CONTEXT_INSUFFICIENT),
        ),
        processing_incomplete=True,
    )

    completeness = json.loads(serialize_explanation_json(result, "source.py"))[
        "completeness"
    ]

    assert completeness == {
        "status": "partial",
        "warnings": [
            {"code": "confidence_downgraded", "section": "symbols"},
            {"code": "context_insufficient", "section": None},
        ],
        "omissions": [
            {"code": "claim_evidence_unavailable", "section": "flow", "count": 3},
            {"code": "claim_unavailable", "section": "purpose", "count": 1},
        ],
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "path",
    [
        "",
        ".",
        "C:/private/source.py",
        "C:folder\\source.py",
        "../source.py",
        "\\\\server\\share\\source.py",
    ],
)
def test_explain_json_rejects_unsafe_paths(path: str) -> None:
    result = ExplanationResult(
        source=SourceFile(Path("source.py"), "source"),
        purpose=(),
        flow=(),
        symbols=(),
        limitations=(),
        context_insufficient=False,
        incomplete=False,
        model="configured-model",
        usage=TokenUsage(1, 1),
        processing_incomplete=False,
    )

    with pytest.raises(ValueError, match="workspace-relative"):
        serialize_explanation_json(result, path)
