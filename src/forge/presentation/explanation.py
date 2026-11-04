"""Render concise explanations with excerpts from the submitted snapshot."""

import re

from forge.domain.explanation import ExplanationClaim, ExplanationResult


def render_explanation(result: ExplanationResult) -> str:
    """Render a plain, auditable explanation without trusting model excerpts."""
    lines = [f"{_safe(result.source.path.name)}: explanation", ""]
    seen: set[str] = set()
    _section(lines, "Purpose", result.purpose, result, seen)
    _section(lines, "Main flow", result.flow, result, seen)
    _section(lines, "Important symbols", result.symbols, result, seen)

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
    seen: set[str],
) -> None:
    lines.append(f"{title}:")
    if not claims:
        lines.append("  None identified.")
        return

    source_lines = result.source.content.splitlines()
    rendered = False
    for claim in claims:
        key = _claim_key(claim.text)
        if claim.symbol is not None:
            key = f"{claim.symbol.casefold()}:{key}"
        if key in seen:
            continue
        seen.add(key)
        rendered = True
        text = (
            f"{claim.symbol}: {claim.text}" if claim.symbol is not None else claim.text
        )
        lines.append(f"  - [{claim.confidence.value}] {_safe(text)}")
        for evidence in claim.evidence:
            lines.append(
                f"    Evidence: {evidence.kind.value} target "
                f"`{_safe(evidence.target)}`, lines "
                f"{evidence.start_line}-{evidence.end_line}"
            )
            for number in range(evidence.start_line, evidence.end_line + 1):
                lines.append(f"      {number:>4} | {_safe(source_lines[number - 1])}")
    if not rendered:
        lines.append("  No distinct claims beyond earlier sections.")


def _claim_key(text: str) -> str:
    """Normalize wording so repeated summaries render only once."""
    return " ".join(word.casefold() for word in re.findall(r"[\w$]+", text))


def _safe(value: str) -> str:
    """Escape terminal controls in source paths, excerpts, and model text."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode()
        for char in value
    )
