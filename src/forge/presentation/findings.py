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

from forge.domain.source import AnalysisResult, Confidence, Finding, Severity

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

    lines = [f"{result.source_path.name}: {_count(result)}", ""]
    for finding in result.by_severity():
        lines.append(f"{_prefix(finding)} {finding.summary}")
        lines.append(f"    {finding.detail}")
        lines.append(f"    confidence: {finding.confidence.value}")
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
        Text.assemble((result.source_path.name, "bold"), f": {_count(result)}")
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
            _finding_text(finding),
        )

    console.print(table)
    console.print(Text(_footer(result), style="dim"))
    return buffer.getvalue()


def _finding_text(finding: Finding) -> Text:
    return Text.assemble(
        (finding.summary, "bold"),
        "\n",
        finding.detail,
        "\n",
        (
            f"confidence: {finding.confidence.value}",
            _confidence_style(finding.confidence),
        ),
    )


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
