"""Plain, evidence-linked rendering for project inspection."""

from forge.domain.project import ProjectFact, ProjectOverview


def render_project_overview(overview: ProjectOverview) -> str:
    """Render observed project facts without reproducing repository content."""
    lines = [f"Project overview: {overview.root}", ""]
    _section(lines, "Guidance", overview.guidance)
    _fact_section(lines, "Languages", overview.languages)
    _fact_section(lines, "Tooling", overview.tooling)
    _fact_section(lines, "Available checks", overview.checks)
    _section(lines, "Project structure (first 2 levels)", overview.directories)
    if overview.omissions:
        lines.extend(["", "Limits and missing evidence:"])
        lines.extend(f"  - {item}" for item in overview.omissions)
    return "\n".join(lines).rstrip() + "\n"


def _section(lines: list[str], title: str, items: tuple[str, ...]) -> None:
    lines.extend([f"{title}:"])
    if items:
        lines.extend(f"  - {item}" for item in items[:20])
        if len(items) > 20:
            lines.append(f"  - and {len(items) - 20} more")
    else:
        lines.append("  - None found")
    lines.append("")


def _fact_section(lines: list[str], title: str, facts: tuple[ProjectFact, ...]) -> None:
    lines.append(f"{title}:")
    if not facts:
        lines.append("  - None identified from included evidence")
    for fact in facts:
        sources = ", ".join(fact.paths[:3])
        if len(fact.paths) > 3:
            sources += f", and {len(fact.paths) - 3} more"
        lines.append(f"  - {fact.name} [evidence: {sources}]")
    lines.append("")
