"""Pure JSON serialization for successful debug and inspect results."""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from forge.domain.project import ProjectOverview
from forge.domain.source import AnalysisResult


class DebugMode(StrEnum):
    """The debug scope selected by the CLI."""

    FILE = "file"
    DIFF = "diff"


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
            "root": ".",
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


def _fact(name: str, paths: tuple[str, ...]) -> dict[str, object]:
    return {"name": name, "evidence": [_safe_relative_path(path) for path in paths]}


def _safe_relative_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if (
        path.is_absolute()
        or ".." in path.parts
        or (path.parts and path.parts[0].endswith(":"))
    ):
        raise ValueError("JSON result paths must be workspace-relative.")
    return path.as_posix()
