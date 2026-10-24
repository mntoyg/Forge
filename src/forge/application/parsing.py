"""Turning a model's reply into findings, without trusting any of it.

ADR-0007: the model is asked for JSON in the prompt, and nothing guarantees it
obliges. This module assumes every field is hostile - missing, the wrong type,
out of range, or empty - and drops what it cannot verify rather than repairing
it.

That last rule is the important one. A parser that "helpfully" clamps a line
number of 900 to the last line of a 40-line file produces a finding that points
somewhere real and is completely wrong. A reader who follows two of those stops
believing the rest, and a code reviewer nobody believes is worse than no
reviewer at all.
"""

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from forge.domain.errors import ProviderResponseError
from forge.domain.review import ChangeSet, ParsedReview, ReviewFile, ReviewFinding
from forge.domain.source import (
    Confidence,
    Finding,
    Location,
    Severity,
    SourceFile,
)

EXCERPT_LIMIT = 200
"""How much of an unusable reply to quote back.

Enough to recognise what the model did - refused, apologised, wrapped the JSON
in something unexpected - without pasting an essay into a terminal.
"""


def parse_findings(text: str, source: SourceFile) -> tuple[Finding, ...]:
    """Extract findings from a model reply.

    ``source`` is needed to validate line numbers: a location is only
    meaningful against the file it points into.

    Returns an empty tuple when the model reports no defects - that is a
    successful analysis, not a failure.

    Raises:
        ProviderResponseError: the reply is not usable JSON, or does not have
            the agreed shape.
    """
    payload = _decode(text)

    raw_findings = payload.get("findings")
    if raw_findings is None:
        raise ProviderResponseError(
            "The model's reply has no 'findings' key. It did not follow the "
            f"requested format. It said: {_excerpt(text)}"
        )
    if not isinstance(raw_findings, list):
        raise ProviderResponseError(
            f"The model's reply has 'findings' as {type(raw_findings).__name__}, "
            "not a list."
        )

    findings = [
        finding
        for item in raw_findings
        if (finding := _to_finding(item, source)) is not None
    ]
    return tuple(findings)


def parse_review_findings(text: str, changes: ChangeSet) -> ParsedReview:
    """Accept only findings tied to a submitted path and a changed snapshot line."""
    try:
        payload = _decode(text)
    except ProviderResponseError:
        # A review response may echo repository content. Never include it in
        # an error message that the CLI will print.
        raise ProviderResponseError(
            "The model's review reply was not usable JSON."
        ) from None
    raw_findings = payload.get("findings")
    if raw_findings is None:
        raise ProviderResponseError("The model's review reply has no 'findings' key.")
    if not isinstance(raw_findings, list):
        raise ProviderResponseError(
            f"The model's reply has 'findings' as {type(raw_findings).__name__}, "
            "not a list."
        )

    by_path = {source.path.as_posix(): source for source in changes.files}
    findings: list[ReviewFinding] = []
    complete = True
    for item in raw_findings:
        finding = _to_review_finding(item, by_path)
        if finding is None:
            complete = False
        else:
            findings.append(finding)
    return ParsedReview(findings=tuple(findings), complete=complete)


def _to_review_finding(
    item: object, sources: Mapping[str, ReviewFile]
) -> ReviewFinding | None:
    """Validate model path and line before constructing evidence from source."""
    if not isinstance(item, dict):
        return None
    raw_path = _text(item.get("path"))
    if not raw_path or "\\" in raw_path or "\x00" in raw_path:
        return None
    normalized = PurePosixPath(raw_path)
    if normalized.is_absolute() or normalized.as_posix() != raw_path:
        return None
    if any(part in {".", ".."} for part in normalized.parts):
        return None
    source = sources.get(raw_path)
    if source is None:
        return None

    line = item.get("line")
    if isinstance(line, bool) or not isinstance(line, int):
        return None
    if line < 1 or line not in source.changed_lines:
        return None
    summary = _text(item.get("summary"))
    detail = _text(item.get("detail"))
    if not summary or not detail:
        return None
    text_lines = source.content.splitlines()
    if line > len(text_lines):
        return None
    return ReviewFinding(
        path=Path(raw_path),
        location=Location(line=line),
        summary=summary,
        detail=detail,
        severity=_severity(item.get("severity")),
        confidence=_confidence(item.get("confidence")),
        evidence=text_lines[line - 1],
    )


def _decode(text: str) -> dict[str, Any]:
    """Decode the reply, tolerating the two things models do anyway.

    They wrap JSON in a markdown fence, and they add a sentence before it.
    Neither is worth failing a run over, so both are stripped before parsing.
    Anything beyond that is a genuine format failure and is reported.
    """
    candidate = _strip_fence(text.strip())

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        extracted = _first_json_object(candidate)
        if extracted is None:
            raise ProviderResponseError(
                "The model's reply was not JSON. Forge asked for a JSON object "
                f"and could not find one. It said: {_excerpt(text)}"
            ) from None
        payload = extracted

    if not isinstance(payload, dict):
        raise ProviderResponseError(
            f"The model's reply was a JSON {type(payload).__name__}, not an "
            f"object. It said: {_excerpt(text)}"
        )
    return payload


def _excerpt(text: str) -> str:
    """Quote enough of a reply to diagnose it, and no more.

    Without this a parse failure says only that it failed, which leaves the
    user with nothing to act on and nothing to report. Whitespace is collapsed
    so a multi-line refusal stays on one line in the terminal.

    The reply is the model's answer about the user's own file, shown back to
    the person who ran the command - it carries no credential, and the key is
    never part of a completion.
    """
    collapsed = " ".join(text.split())
    if not collapsed:
        return "(nothing at all)"
    if len(collapsed) <= EXCERPT_LIMIT:
        return repr(collapsed)
    return repr(collapsed[:EXCERPT_LIMIT] + "...")


def _strip_fence(text: str) -> str:
    """Remove a ```json ... ``` wrapper if the model added one."""
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    body = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
    return "\n".join(body).strip()


def _first_json_object(text: str) -> dict[str, Any] | None:
    """Find the first balanced ``{...}`` and decode it.

    Brace counting rather than a regular expression, because the values can
    contain braces - a finding about a dict literal, for instance. String
    contents are skipped so that a brace inside a message does not unbalance
    the count.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    decoded = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return decoded if isinstance(decoded, dict) else None
    return None


def _to_finding(item: object, source: SourceFile) -> Finding | None:
    """Convert one raw entry into a finding, or drop it.

    Returning ``None`` rather than raising is deliberate: one malformed entry
    among five should cost the user that entry, not the whole run.
    """
    if not isinstance(item, dict):
        return None

    summary = _text(item.get("summary"))
    detail = _text(item.get("detail"))
    if not summary or not detail:
        return None

    return Finding(
        summary=summary,
        detail=detail,
        severity=_severity(item.get("severity")),
        confidence=_confidence(item.get("confidence")),
        location=_location(item.get("line"), source),
    )


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _severity(value: object) -> Severity:
    """Read a severity, defaulting to MEDIUM when it is not one we know.

    Defaulting is safe here in a way it is not for a line number: an unknown
    severity costs the reader a little sorting accuracy, while an unknown line
    would send them to the wrong place.
    """
    if isinstance(value, str):
        try:
            return Severity(value.strip().lower())
        except ValueError:
            return Severity.MEDIUM
    return Severity.MEDIUM


def _confidence(value: object) -> Confidence:
    """Read a confidence, defaulting to POSSIBLE when unknown.

    The default is the *least* certain value on purpose. A model that failed to
    state its confidence has not earned the reader's.
    """
    if isinstance(value, str):
        try:
            return Confidence(value.strip().lower())
        except ValueError:
            return Confidence.POSSIBLE
    return Confidence.POSSIBLE


def _location(value: object, source: SourceFile) -> Location | None:
    """Read a line number, or return no location at all.

    A line outside the file is dropped rather than clamped. ``bool`` is
    excluded explicitly because in Python ``True`` is an ``int``, and "line
    True" would otherwise become line 1.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not 1 <= value <= source.line_count:
        return None
    return Location(line=value)
