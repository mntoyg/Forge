"""Preflight checks for cutting a release.

Usage::

    uv run python scripts/release.py 0.1.0

This script deliberately does *not* tag, publish, or push anything. It verifies
that the repository is in a releasable state and prints the commands a
maintainer should run. Releases are a human decision; see
``.forge/workflows/release.md``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _problems(version: str) -> list[str]:
    problems: list[str] = []

    if not SEMVER.match(version):
        problems.append(f"'{version}' is not a valid semantic version.")

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if f'version = "{version}"' not in pyproject:
        problems.append(f"pyproject.toml does not declare version {version}.")

    init = (ROOT / "src" / "forge" / "__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in init:
        problems.append(f"src/forge/__init__.py does not declare version {version}.")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:
        problems.append(f"CHANGELOG.md has no '## [{version}]' section.")

    status = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        problems.append("Working tree is dirty; commit or stash first.")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Version being released, e.g. 0.1.0")
    args = parser.parse_args(argv)

    problems = _problems(args.version)
    if problems:
        print("Not ready to release:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"Ready to release {args.version}. Run:")
    print(f"  git tag -a v{args.version} -m 'Release v{args.version}'")
    print(f"  git push origin v{args.version}")
    print("The release workflow takes over from the tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
