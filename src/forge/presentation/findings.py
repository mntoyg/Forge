"""Rendering an analysis result for a human.

Two renderers, one shape of output. The Rich one is for a terminal a person is
looking at; the plain one is for a pipe, a log, or a CI transcript, where
escape codes and box drawing are noise at best and corruption at worst.

Both are pure functions of their input. They decide nothing - which is why the
choice between them is made in `cli/`, and why they can be tested by asserting
on a string.
"""

import io

from rich.console import Console
from rich.table import Table
from rich.text import Text

from forge.domain.source import (
    AnalysisResult,
    Confidence,
    FileHistory,
    Finding,
    Severity,
)

_SEVERITY_STYLE = {
    Severity.HIGH: "bold red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "dim",
}

_SEVERITY_LABEL = {
    Severity.HIGH: "HIGH",
    Severity.MEDIUM: "MEDIUM",
    Severity.LOW: "LOW",
}


def render_plain(result: AnalysisResult) -> str:
    """Render without colour, boxes, or escape codes."""
    if not result.has_findings:
        return f"{result.source_path.name}: no findings.\n{_footer(result)}"

    lines = [f"{result.source_path.name}: {_count(result)}{_churn(result.history)}", ""]
    for finding in result.by_severity():
        lines.append(f"{_prefix(finding)} {finding.summary}")
        lines.append(f"    {finding.detail}")
        lines.append(f"    confidence: {finding.confidence.value}")
        note = _history_note(result.history, finding)
        if note is not None:
            lines.append(f"    {note}")
        lines.append("")
    lines.append(_footer(result))
    return "\n".join(lines)


def render_rich(result: AnalysisResult, *, width: int | None = None) -> str:
    """Render for a terminal, returning the string rather than printing it.

    Returning a string keeps this a pure function: the caller decides where
    output goes, and a test can read what was produced without capturing
    stdout.
    """
    buffer = io.StringIO()
    console = Console(
        file=buffer,
        width=width or 100,
        force_terminal=False,
        highlight=False,
    )

    if not result.has_findings:
        console.print(
            Text.assemble(
                (result.source_path.name, "bold"),
                ": ",
                ("no findings", "green"),
                ".",
            )
        )
        console.print(Text(_footer(result), style="dim"))
        return buffer.getvalue()

    console.print(
        Text.assemble(
            (result.source_path.name, "bold"),
            f": {_count(result)}{_churn(result.history)}",
        )
    )
    console.print()

    table = Table(show_header=True, header_style="bold", expand=False, pad_edge=False)
    table.add_column("Severity", no_wrap=True)
    table.add_column("Line", justify="right", no_wrap=True)
    table.add_column("Finding", overflow="fold")

    for finding in result.by_severity():
        table.add_row(
            Text(
                _SEVERITY_LABEL[finding.severity],
                style=_SEVERITY_STYLE[finding.severity],
            ),
            str(finding.location.line) if finding.location else "-",
            _finding_text(finding, result.history),
        )

    console.print(table)
    console.print(Text(_footer(result), style="dim"))
    return buffer.getvalue()


def _finding_text(finding: Finding, history: FileHistory | None) -> Text:
    text = Text.assemble(
        (finding.summary, "bold"),
        "\n",
        finding.detail,
        "\n",
        (
            f"confidence: {finding.confidence.value}",
            _confidence_style(finding.confidence),
        ),
    )
    note = _history_note(history, finding)
    if note is not None:
        text.append("\n")
        text.append(note, style="dim")
    return text


def _history_note(history: FileHistory | None, finding: Finding) -> str | None:
    """One line of version-control fact about where this finding points.

    ``None`` when there is nothing honest to say: no repository was reachable,
    or the finding cites no line to look up. A line that exists but has no
    commit behind it is a different answer, not a missing one - the developer
    wrote it and has not committed it - so it says so.

    The date is written out rather than rendered as "3 days ago". Relative time
    needs a clock, which would make this function's output depend on when it
    ran; a date is the same fact and stays true in a log read next month.
    """
    if history is None or finding.location is None:
        return None

    record = history.at(finding.location.line)
    if record is None:
        return "history: not committed yet"
    return (
        f"history: last changed {record.changed_on.isoformat()} "
        f"by {record.author} ({record.commit})"
    )


def _churn(history: FileHistory | None) -> str:
    """How much the whole file has been moving, as a note on the header.

    Beside the findings rather than inside one, because it is a property of the
    file: a line last touched a year ago in a file nobody edits is a different
    risk from the same line in a file that changed nine times this quarter.
    """
    if history is None:
        return ""

    commits = history.recent_commits
    plural = "" if commits == 1 else "s"
    return f" ({commits} commit{plural} in the last {history.window_days} days)"


def _confidence_style(confidence: Confidence) -> str:
    """Dim the uncertain ones.

    The vision commits to honest output: a "possible" finding should not carry
    the same visual weight as a "certain" one, or the distinction is decorative.
    """
    return {
        Confidence.CERTAIN: "dim",
        Confidence.LIKELY: "dim",
        Confidence.POSSIBLE: "dim italic",
    }[confidence]


def _prefix(finding: Finding) -> str:
    location = f"line {finding.location.line}" if finding.location else "no line"
    return f"[{_SEVERITY_LABEL[finding.severity]}] ({location})"


def _count(result: AnalysisResult) -> str:
    total = len(result.findings)
    return f"{total} finding{'s' if total != 1 else ''}"


def _footer(result: AnalysisResult) -> str:
    """State the model and the cost.

    Both are here because the user paid for the call, and because "which model
    said this" is the first question anyone asks about a surprising finding.
    """
    usage = result.usage
    return (
        f"model: {result.model} | "
        f"tokens: {usage.input_tokens:,} in, {usage.output_tokens:,} out"
    )
