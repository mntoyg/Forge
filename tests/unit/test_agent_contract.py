"""The agent handover contract, enforced rather than merely written down.

Several AI tools work in this repository, each starting from nothing. The
files checked here are how a fresh session learns what is true. A rule about
them that only exists in prose is a rule that erodes, so the two that actually
matter are checked mechanically:

1. Every entry point exists and points at the one source of truth.
2. The handover file stays short enough to be read.
"""

from pathlib import Path

import pytest

import forge

ROOT = Path(forge.__file__).resolve().parents[2]

STATUS = ROOT / ".forge" / "context" / "status.md"
AGENTS = ROOT / "AGENTS.md"
NEXT_PROMPT = ROOT / ".forge" / "NEXT_PROMPT.md"

STATUS_LINE_BUDGET = 150
"""The limit `status.md` sets for itself.

A sibling project accumulated a 13,000-line progress log. No agent could read
it without exhausting its context window, which made it worse than having no
notes at all. Length here is a defect, not thoroughness.
"""

NEXT_PROMPT_LINE_BUDGET = 200
"""The limit the next-chat prompt sets for itself, for the same reason as
status.md: each chat rewrites it, and a file every generation adds to is a
file no generation can read."""

HANDOFF_LOOP_MARKERS = ("The handoff loop", "70%", "get_usage", "NEXT_PROMPT.md")
"""What the prompt must still say for the next chat to write the one after it."""

ENTRY_POINTS = [
    "CLAUDE.md",
    ".cursorrules",
    ".aider.conf.yml",
]


@pytest.mark.unit
def test_the_entry_point_exists() -> None:
    assert AGENTS.is_file(), "AGENTS.md is what every tool is pointed at"


@pytest.mark.unit
@pytest.mark.parametrize("name", ENTRY_POINTS)
def test_every_tool_entry_point_points_at_agents_md(name: str) -> None:
    """Each tool reads a different filename; none of them repeats the rules.

    A copy per tool is a copy that drifts, and a tool acting on last month's
    rules is worse than one with none.
    """
    path = ROOT / name

    assert path.is_file(), f"{name} is missing"
    assert "AGENTS.md" in path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_the_handover_file_exists() -> None:
    assert STATUS.is_file()


@pytest.mark.unit
def test_the_handover_file_stays_readable() -> None:
    """Enforces the budget `status.md` sets for itself.

    If this fails, the fix is to delete what is no longer true - not to raise
    the number. History belongs in git log and CHANGELOG.md.
    """
    lines = len(STATUS.read_text(encoding="utf-8").splitlines())

    assert lines <= STATUS_LINE_BUDGET, (
        f"status.md is {lines} lines, over its own {STATUS_LINE_BUDGET}-line "
        "budget. Remove what has stopped being true rather than raising this."
    )


@pytest.mark.unit
def test_the_handover_file_records_when_it_was_verified() -> None:
    """A status file with no date cannot be told apart from a stale one."""
    assert "Last verified:" in STATUS.read_text(encoding="utf-8")


@pytest.mark.unit
def test_the_reading_order_names_the_handover_file() -> None:
    """An agent that never opens status.md starts from stale assumptions."""
    assert "status.md" in AGENTS.read_text(encoding="utf-8")


@pytest.mark.unit
def test_the_next_chat_prompt_exists() -> None:
    assert NEXT_PROMPT.is_file()


@pytest.mark.unit
def test_the_next_chat_prompt_stays_readable() -> None:
    """Every chat rewrites it. Compress rather than raise this number."""
    lines = len(NEXT_PROMPT.read_text(encoding="utf-8").splitlines())

    assert lines <= NEXT_PROMPT_LINE_BUDGET, (
        f"NEXT_PROMPT.md is {lines} lines, over its {NEXT_PROMPT_LINE_BUDGET}-line "
        "budget. Delete lessons that are obsolete or enforced elsewhere."
    )


@pytest.mark.unit
@pytest.mark.parametrize("marker", HANDOFF_LOOP_MARKERS)
def test_the_next_chat_prompt_still_carries_the_handoff_loop(marker: str) -> None:
    """The loop is what gets the next prompt written at all.

    A generation that drops it ends the chain without anyone noticing: the chat
    that reads it simply never hands off. Its absence fails the build instead.
    """
    assert marker in NEXT_PROMPT.read_text(encoding="utf-8")


@pytest.mark.unit
def test_the_next_chat_prompt_says_which_generation_it_is() -> None:
    """Without it, two versions of the prompt cannot be told apart."""
    assert "Generation" in NEXT_PROMPT.read_text(encoding="utf-8")


@pytest.mark.unit
def test_the_entry_point_names_the_handoff_loop() -> None:
    """An agent that starts from AGENTS.md, not from a pasted prompt, still
    needs to know the loop exists."""
    assert "NEXT_PROMPT.md" in AGENTS.read_text(encoding="utf-8")
