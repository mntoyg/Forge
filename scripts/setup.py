"""Bootstrap a local development environment.

Usage::

    uv run python scripts/setup.py

This is a developer convenience wrapper, not a packaging script. Packaging
metadata lives in ``pyproject.toml``; ``uv`` is the build and dependency tool.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(*command: str) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    if shutil.which("uv") is None:
        print(
            "uv is not on PATH. Install it first: https://docs.astral.sh/uv/",
            file=sys.stderr,
        )
        return 1

    _run("uv", "sync", "--all-groups")

    env_example = ROOT / ".env.example"
    env_file = ROOT / ".env"
    if env_example.exists() and not env_file.exists():
        env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
        print("Created .env from .env.example - fill in your values.")

    print("\nEnvironment ready. Next: uv run python scripts/check.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
