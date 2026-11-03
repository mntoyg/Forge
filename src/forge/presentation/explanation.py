"""Render source explanations with excerpts from the submitted snapshot."""

from forge.domain.explanation import ExplanationClaim, ExplanationResult


def render_explanation(result: ExplanationResult) -> str:
    """Render a plain, auditable explanation without trusting model excerpts."""
    lines = [f"{_safe(result.source.path.name)}: explanation", ""]
    _section(lines, "Purpose", result.purpose, result)
    _section(lines, "Main flow", result.flow, result)
    _section(lines, "Important symbols", result.symbols, result)

    if result.limitations:
        lines.extend(["Limitations:"])
        lines.extend(f"  - {_safe(item)}" for item in result.limitations)
    if result.incomplete:
        lines.append(
            "Incomplete: some claims were omitted or context is missing; "
            "verify this explanation against the code."
        )
    else:
        lines.append(
            "AI-generated explanation; citations show source locations, "
            "not proof that an interpretation is correct."
        )
    lines.append(
        f"Model: {_safe(result.model)} | tokens: "
        f"{result.usage.input_tokens:,} in, {result.usage.output_tokens:,} out"
    )
    return "\n".join(lines) + "\n"


def _section(
    lines: list[str],
    title: str,
    claims: tuple[ExplanationClaim, ...],
    result: ExplanationResult,
) -> None:
    lines.append(f"{title}:")
    if not claims:
        lines.append("  No grounded claims supplied.")
        return

    source_lines = result.source.content.splitlines()
    for claim in claims:
        lines.append(f"  - [{claim.confidence.value}] {_safe(claim.text)}")
        for evidence in claim.evidence:
            lines.append(
                f"    Evidence: lines {evidence.start_line}-{evidence.end_line}"
            )
            for number in range(evidence.start_line, evidence.end_line + 1):
                lines.append(f"      {number:>4} | {_safe(source_lines[number - 1])}")


def _safe(value: str) -> str:
    """Escape terminal controls in source paths, excerpts, and model text."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode()
        for char in value
    )
