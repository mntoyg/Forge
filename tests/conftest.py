"""Shared pytest fixtures.

Keep fixtures here deterministic. Anything that would reach the network, spend
money, or depend on wall-clock time belongs in a test-local fake instead.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge.infrastructure.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_forge_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """Cut every test off from the developer's local configuration.

    Three things leak in without this, and all three make a suite that passes
    on one machine and fails on another:

    1. ``FORGE_*`` variables already in the environment.
    2. A ``.env`` file in the repository root, which Pydantic Settings reads
       relative to the working directory - so the fix is to run each test
       somewhere that has no ``.env``.
    3. Settings cached from an earlier test in the same process.

    Running in ``tmp_path`` also enforces the rule that no test writes into the
    repository.
    """
    for key in [k for k in os.environ if k.startswith("FORGE_")]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
