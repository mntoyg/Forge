"""Plain, evidence-bound output for a bounded change review."""

from pathlib import Path

from forge.application.review import ReviewPlan
from forge.domain.review import ReviewResult


def render_review_plan(plan: ReviewPlan) -> str:
    """Show the exact local scope and cost estimate before consent."""
    lines = [
        "Review plan:",
        f"  Model: {_safe(plan.model)}",
        f"  Request: {plan.request_bytes:,} UTF-8 bytes; about "
        f"{plan.approximate_tokens:,} input tokens",
        "  Provider calls: at most 1 billable call; source is sent after consent.",
        "  AI review may miss defects; secret detection is heuristic.",
        "Included paths:",
    ]
    if plan.changes.files:
        lines.extend(
            f"  - {_display_path(item.previous_path, item.path)}"
            for item in plan.changes.files
        )
    else:
        lines.append("  - None")
    lines.append("Omitted paths:")
    if plan.changes.omissions:
        lines.extend(
            f"  - {_display_path(item.previous_path, item.path)} ({item.reason.value})"
            for item in plan.changes.omissions
        )
    else:
        lines.append("  - None")
    return "\n".join(lines) + "\n"


def render_review_result(result: ReviewResult) -> str:
    """Render validated findings and the provider's measured token usage."""
    lines = ["Review findings:"]
    if result.findings:
        for finding in result.findings:
            lines.extend(
                [
                    f"  [{finding.severity.value.upper()}] "
                    f"{_safe(finding.path.as_posix())}:line {finding.location.line} "
                    f"{_safe(finding.summary)}",
                    f"    {_safe(finding.detail)}",
                    f"    Evidence: {_safe(finding.evidence)}",
                ]
            )
    else:
        lines.append("  No findings reported.")
    if result.incomplete:
        lines.append(
            "Coverage is incomplete; review the omissions and findings carefully."
        )
    else:
        lines.append(
            "AI review may miss defects; this is not a completeness guarantee."
        )
    if result.omissions:
        lines.append("Omissions:")
        lines.extend(
            f"  - {_display_path(item.previous_path, item.path)} ({item.reason.value})"
            for item in result.omissions
        )
    lines.append(
        f"Model: {_safe(result.model)} | tokens: {result.usage.input_tokens:,} in, "
        f"{result.usage.output_tokens:,} out"
    )
    return "\n".join(lines) + "\n"


def _display_path(previous: Path | None, current: Path) -> str:
    """Represent rename paths without interpreting repository-controlled text."""
    if previous is None:
        return _safe(current.as_posix())
    return f"{_safe(previous.as_posix())} -> {_safe(current.as_posix())}"


def _safe(value: str) -> str:
    """Escape terminal control characters in repository and model data."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode()
        for char in value
    )
