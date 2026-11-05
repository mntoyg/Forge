"""Pure JSON serialization for successful results and safe command errors."""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath

from forge.domain.explanation import (
    ExplanationClaim,
    ExplanationDiagnosticKind,
    ExplanationResult,
)
from forge.domain.project import ProjectOverview
from forge.domain.source import AnalysisResult


class DebugMode(StrEnum):
    """The debug scope selected by the CLI."""

    FILE = "file"
    DIFF = "diff"


class JsonCommand(StrEnum):
    """Commands included in the approved v1 JSON output contract."""

    DEBUG = "debug"
    INSPECT = "inspect"
    EXPLAIN = "explain"


class JsonErrorCode(StrEnum):
    """Stable JSON error codes corresponding to ADR-0006 exit-code classes."""

    RESULT_UNAVAILABLE = "result_unavailable"
    INPUT_UNUSABLE = "input_unusable"
    NOT_CONFIGURED = "not_configured"
    PROVIDER_FAILED = "provider_failed"


_ERROR_MESSAGES = {
    JsonErrorCode.RESULT_UNAVAILABLE: "Forge could not produce a usable result.",
    JsonErrorCode.INPUT_UNUSABLE: "The requested input could not be used.",
    JsonErrorCode.NOT_CONFIGURED: "Forge is not configured for this command.",
    JsonErrorCode.PROVIDER_FAILED: "The configured provider could not complete the request.",
}


@dataclass(frozen=True, slots=True)
class DebugJsonInput:
    """Presentation context missing from the domain analysis result."""

    analysis: AnalysisResult
    path: str
    mode: DebugMode
    whole_file_size_warning: bool = False


def serialize_debug_json(value: DebugJsonInput) -> str:
    """Serialize a successful debug result without touching CLI or the system."""
    path = _safe_relative_path(value.path)
    result = value.analysis
    warnings = (
        [{"code": "whole_file_size_limit"}] if value.whole_file_size_warning else []
    )
    omissions = [{"code": "provider_findings_discarded"}] if result.incomplete else []
    completeness = "partial" if warnings or omissions else "complete"
    history = None
    if result.history is not None:
        history = {
            "recent_commits": result.history.recent_commits,
            "window_days": result.history.window_days,
            "records": [
                {
                    "line": item.line,
                    "commit": item.commit,
                    "author": item.author,
                    "changed_on": item.changed_on.isoformat(),
                }
                for item in result.history.records
            ],
        }
    payload = {
        "schema_version": 1,
        "command": "debug",
        "status": "success",
        "result": {
            "path": path,
            "mode": value.mode.value,
            "findings": [
                {
                    "summary": item.summary,
                    "detail": item.detail,
                    "severity": item.severity.value,
                    "confidence": item.confidence.value,
                    "location": (
                        {"line": item.location.line}
                        if item.location is not None
                        else None
                    ),
                }
                for item in result.findings
            ],
            "history": history,
            "model": result.model,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        },
        "completeness": {
            "status": completeness,
            "warnings": warnings,
            "omissions": omissions,
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def serialize_error_json(command: JsonCommand, code: JsonErrorCode) -> str:
    """Serialize a safe v1 error without accepting exception or provider text."""
    payload = {
        "schema_version": 1,
        "command": command.value,
        "status": "error",
        "error": {"code": code.value, "message": _ERROR_MESSAGES[code]},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def serialize_inspect_json(overview: ProjectOverview) -> str:
    """Serialize bounded inspect evidence using only its typed result fields."""
    omissions = [
        {
            "code": item.code.value,
            **({"path": _safe_relative_path(item.path)} if item.path else {}),
        }
        for item in overview.structured_omissions
    ]
    payload = {
        "schema_version": 1,
        "command": "inspect",
        "status": "success",
        "result": {
            "root": overview.root.name or ".",
            "guidance": [_safe_relative_path(path) for path in overview.guidance],
            "languages": [_fact(item.name, item.paths) for item in overview.languages],
            "tooling": [_fact(item.name, item.paths) for item in overview.tooling],
            "checks": [_fact(item.name, item.paths) for item in overview.checks],
            "directories": [_safe_relative_path(path) for path in overview.directories],
        },
        "completeness": {
            "status": "complete" if overview.scan_complete else "partial",
            "warnings": [],
            "omissions": omissions,
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


_EXPLANATION_OMISSIONS = {
    ExplanationDiagnosticKind.SECTION_MISSING: ("section_unavailable", True),
    ExplanationDiagnosticKind.SECTION_MALFORMED: ("section_unavailable", True),
    ExplanationDiagnosticKind.CLAIM_MALFORMED: ("claim_unavailable", True),
    ExplanationDiagnosticKind.SUBJECT_UNAVAILABLE: ("symbol_unavailable", True),
    ExplanationDiagnosticKind.EVIDENCE_MALFORMED: ("claim_evidence_unavailable", True),
    ExplanationDiagnosticKind.EVIDENCE_KIND_UNSUPPORTED: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.EVIDENCE_TARGET_SHAPE_UNSUPPORTED: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.EVIDENCE_TARGET_NOT_FOUND: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.EVIDENCE_SOURCE_SHAPE_MISMATCH: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.EVIDENCE_VALIDATION_UNAVAILABLE: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.CALL_TARGET_IS_DECLARATION: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.CALL_EXPRESSION_NOT_FOUND: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.SYMBOL_OPERATION_DISALLOWED: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.EVIDENCE_OUT_OF_SCOPE: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.PURPOSE_CALL_NOT_IN_FLOW: (
        "claim_evidence_unavailable",
        True,
    ),
    ExplanationDiagnosticKind.NAME_ONLY: ("symbol_description_unavailable", True),
    ExplanationDiagnosticKind.LIMITATIONS_MISSING: ("limitations_unavailable", False),
    ExplanationDiagnosticKind.LIMITATIONS_FIELD_MALFORMED: (
        "limitations_unavailable",
        False,
    ),
    ExplanationDiagnosticKind.LIMITATIONS_MALFORMED: (
        "limitation_entry_unavailable",
        False,
    ),
    ExplanationDiagnosticKind.CONTEXT_STATUS_MISSING: (
        "context_status_unavailable",
        False,
    ),
    ExplanationDiagnosticKind.CONTEXT_STATUS_MALFORMED: (
        "context_status_unavailable",
        False,
    ),
}

_EXPLANATION_WARNINGS = {
    ExplanationDiagnosticKind.CONFIDENCE_UNRECOGNIZED: "confidence_downgraded",
    ExplanationDiagnosticKind.CONTEXT_INSUFFICIENT: "context_insufficient",
    ExplanationDiagnosticKind.SOURCE_VALIDATION_UNAVAILABLE: "source_validation_unavailable",
    ExplanationDiagnosticKind.SYMBOL_VALIDATION_UNAVAILABLE: "symbol_validation_unavailable",
}


def serialize_explanation_json(result: ExplanationResult, path: str) -> str:
    """Serialize validated explanation data without accessing its source or environment."""
    safe_path = _safe_relative_path(path)
    if not path.strip() or safe_path == ".":
        raise ValueError("JSON result paths must be workspace-relative.")

    warning_keys: set[tuple[str, str | None]] = set()
    omission_counts: dict[tuple[str, str | None], int] = {}
    diagnostics = []
    for diagnostic in result.diagnostics:
        section = diagnostic.section.value if diagnostic.section is not None else None
        diagnostics.append(
            {
                "section": section,
                "kind": diagnostic.kind.value,
                "count": diagnostic.count,
            }
        )
        if diagnostic.kind in _EXPLANATION_OMISSIONS:
            code, include_section = _EXPLANATION_OMISSIONS[diagnostic.kind]
            key = (code, section if include_section else None)
            omission_counts[key] = omission_counts.get(key, 0) + diagnostic.count
        elif diagnostic.kind in _EXPLANATION_WARNINGS:
            warning_keys.add((_EXPLANATION_WARNINGS[diagnostic.kind], section))

    if result.context_insufficient:
        warning_keys.add(("context_insufficient", None))
    if result.limitations:
        warning_keys.add(("limitation_present", None))

    warnings = [
        {"code": code, "section": section}
        for code, section in sorted(
            warning_keys, key=lambda item: (item[0], item[1] or "")
        )
    ]
    omissions = [
        {"code": code, "section": section, "count": count}
        for (code, section), count in sorted(
            omission_counts.items(), key=lambda item: (item[0][0], item[0][1] or "")
        )
    ]
    if omissions:
        completeness = "partial"
    elif result.processing_incomplete is True:
        raise ValueError(
            "An incomplete explanation needs a stable omission diagnostic."
        )
    elif result.processing_incomplete is None or any(
        diagnostic.kind
        in {
            ExplanationDiagnosticKind.SOURCE_VALIDATION_UNAVAILABLE,
            ExplanationDiagnosticKind.SYMBOL_VALIDATION_UNAVAILABLE,
        }
        for diagnostic in result.diagnostics
    ):
        completeness = "unknown"
    else:
        completeness = "complete"

    payload = {
        "schema_version": 1,
        "command": "explain",
        "status": "success",
        "result": {
            "path": safe_path,
            "purpose": [
                _explanation_claim(item, include_symbol=False)
                for item in result.purpose
            ],
            "main_flow": [
                _explanation_claim(item, include_symbol=False) for item in result.flow
            ],
            "important_symbols": [
                _explanation_claim(item, include_symbol=True) for item in result.symbols
            ],
            "limitations": list(result.limitations),
            "context_insufficient": result.context_insufficient,
            "incomplete": result.incomplete,
            "model": result.model,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
            "diagnostics": diagnostics,
        },
        "completeness": {
            "status": completeness,
            "warnings": warnings,
            "omissions": omissions,
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _explanation_claim(
    claim: ExplanationClaim, *, include_symbol: bool
) -> dict[str, object]:
    """Convert a validated domain claim to its approved JSON fields."""
    if include_symbol and claim.symbol is None:
        raise ValueError("An important-symbol claim must identify its symbol.")

    value: dict[str, object] = {
        "text": claim.text,
        "confidence": claim.confidence.value,
        "evidence": [
            {
                "kind": item.kind.value,
                "target": item.target,
                "start_line": item.start_line,
                "end_line": item.end_line,
            }
            for item in claim.evidence
        ],
    }
    if include_symbol:
        value["symbol"] = claim.symbol
    return value


def _fact(name: str, paths: tuple[str, ...]) -> dict[str, object]:
    return {"name": name, "evidence": [_safe_relative_path(path) for path in paths]}


def _safe_relative_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    windows_path = PureWindowsPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or windows_path.drive
        or windows_path.root
    ):
        raise ValueError("JSON result paths must be workspace-relative.")
    return path.as_posix()
