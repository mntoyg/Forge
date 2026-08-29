"""Run the full local quality gate.

Usage::

    uv run python scripts/check.py           # run everything, report at the end
    uv run python scripts/check.py --fix     # let the formatter and linter fix

The same four checks run in CI, in the same order. Keeping one entry point
means "it passed locally" and "it passed in CI" cannot drift apart.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]


def _checks(*, fix: bool) -> list[Check]:
    black = (
        ("uv", "run", "black", ".") if fix else ("uv", "run", "black", "--check", ".")
    )
    ruff = (
        ("uv", "run", "ruff", "check", "--fix", ".")
        if fix
        else ("uv", "run", "ruff", "check", ".")
    )
    return [
        Check("format (black)", black),
        Check("lint (ruff)", ruff),
        Check("types (mypy)", ("uv", "run", "mypy")),
        Check("tests (pytest)", ("uv", "run", "pytest")),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply formatter and linter fixes instead of only reporting.",
    )
    args = parser.parse_args(argv)

    failures: list[str] = []
    for check in _checks(fix=args.fix):
        print(f"\n=== {check.name} ===")
        result = subprocess.run(check.command, cwd=ROOT, check=False)
        if result.returncode != 0:
            failures.append(check.name)

    print("\n" + "=" * 40)
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
