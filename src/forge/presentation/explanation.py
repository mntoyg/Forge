"""Render concise explanations with excerpts from the submitted snapshot."""

import re

from forge.domain.explanation import (
    ExplanationClaim,
    ExplanationDiagnostic,
    ExplanationDiagnosticKind,
    ExplanationResult,
    ExplanationSection,
)


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
    if result.diagnostics:
        lines.append("Analysis notes:")
        lines.extend(f"  - {_diagnostic_text(item)}" for item in result.diagnostics)
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


def _diagnostic_text(diagnostic: ExplanationDiagnostic) -> str:
    """Render only fixed diagnostic categories, never provider-controlled data."""
    section = _section_name(diagnostic.section)
    count = diagnostic.count
    plural = "s" if count != 1 else ""
    verb = "were" if count != 1 else "was"
    claim_type = _claim_type(diagnostic.section)
    kind = diagnostic.kind
    if kind is ExplanationDiagnosticKind.SECTION_EMPTY:
        return f"No claims were returned for {section}."
    if kind is ExplanationDiagnosticKind.SECTION_MISSING:
        return f"The {section} section was missing."
    if kind is ExplanationDiagnosticKind.SECTION_MALFORMED:
        return (
            f"The {section} section was malformed; its claims could not be validated."
        )
    if kind is ExplanationDiagnosticKind.CLAIM_MALFORMED:
        return f"{count} {claim_type} claim{plural} {verb} malformed and omitted."
    if kind is ExplanationDiagnosticKind.SUBJECT_UNAVAILABLE:
        return (
            f"{count} symbol claim{plural} {verb} omitted because a unique "
            "subject could not be resolved."
        )
    if kind is ExplanationDiagnosticKind.EVIDENCE_MALFORMED:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because evidence "
            "was malformed or its line range was invalid."
        )
    if kind is ExplanationDiagnosticKind.EVIDENCE_KIND_UNSUPPORTED:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because the anchor "
            "kind was unsupported."
        )
    if kind is ExplanationDiagnosticKind.EVIDENCE_TARGET_SHAPE_UNSUPPORTED:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because the target "
            "shape was unsupported."
        )
    if kind is ExplanationDiagnosticKind.EVIDENCE_TARGET_NOT_FOUND:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because the target "
            "did not match executable tokens in the cited lines."
        )
    if kind is ExplanationDiagnosticKind.EVIDENCE_SOURCE_SHAPE_MISMATCH:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because the target "
            "did not match the required source shape for its anchor kind."
        )
    if kind is ExplanationDiagnosticKind.EVIDENCE_VALIDATION_UNAVAILABLE:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because evidence "
            "could not be validated for this source."
        )
    if kind is ExplanationDiagnosticKind.CALL_TARGET_IS_DECLARATION:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because the call "
            "target matched a function declaration, not a call expression."
        )
    if kind is ExplanationDiagnosticKind.CALL_EXPRESSION_NOT_FOUND:
        return (
            f"{count} {claim_type} claim{plural} {verb} omitted because a call "
            "expression could not be confirmed in the cited lines."
        )
    if kind is ExplanationDiagnosticKind.SYMBOL_OPERATION_DISALLOWED:
        return (
            f"{count} symbol claim{plural} {verb} omitted because symbol claims "
            "cannot use operation anchors."
        )
    if kind is ExplanationDiagnosticKind.EVIDENCE_OUT_OF_SCOPE:
        return (
            f"{count} symbol claim{plural} {verb} omitted because evidence fell "
            "outside the declared subject scope."
        )
    if kind is ExplanationDiagnosticKind.PURPOSE_CALL_NOT_IN_FLOW:
        return (
            f"{count} purpose claim{plural} {verb} omitted because no identical "
            "call anchor was validated in Main flow."
        )
    if kind is ExplanationDiagnosticKind.NAME_ONLY:
        return (
            f"{count} symbol claim{plural} {verb} omitted because the claim only "
            "repeated the symbol name."
        )
    if kind is ExplanationDiagnosticKind.CONFIDENCE_UNRECOGNIZED:
        return (
            f"{count} {claim_type} claim{plural} had an unrecognized "
            "confidence label and is shown as possible."
        )
    if kind is ExplanationDiagnosticKind.LIMITATIONS_MALFORMED:
        return f"{count} limitation item{plural} {verb} malformed and omitted."
    if kind is ExplanationDiagnosticKind.LIMITATIONS_MISSING:
        return "The limitations field was missing."
    if kind is ExplanationDiagnosticKind.LIMITATIONS_FIELD_MALFORMED:
        return "The limitations field was malformed."
    if kind is ExplanationDiagnosticKind.CONTEXT_STATUS_MISSING:
        return "The context completeness status was missing."
    if kind is ExplanationDiagnosticKind.CONTEXT_STATUS_MALFORMED:
        return "The context completeness status was malformed."
    if kind is ExplanationDiagnosticKind.CONTEXT_INSUFFICIENT:
        return "The provider reported that context was insufficient."
    raise AssertionError(f"Unhandled explanation diagnostic: {kind}")


def _section_name(section: ExplanationSection | None) -> str:
    if section is ExplanationSection.PURPOSE:
        return "Purpose"
    if section is ExplanationSection.FLOW:
        return "Main flow"
    if section is ExplanationSection.SYMBOLS:
        return "Important symbols"
    return "explanation"


def _claim_type(section: ExplanationSection | None) -> str:
    if section is ExplanationSection.PURPOSE:
        return "purpose"
    if section is ExplanationSection.FLOW:
        return "flow"
    if section is ExplanationSection.SYMBOLS:
        return "symbol"
    return "explanation"


def _safe(value: str) -> str:
    """Escape terminal controls in source paths, excerpts, and model text."""
    return "".join(
        char if char.isprintable() else char.encode("unicode_escape").decode()
        for char in value
    )
