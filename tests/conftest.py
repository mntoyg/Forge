"""Shared pytest fixtures.

Keep fixtures here deterministic. Anything that would reach the network, spend
money, or depend on wall-clock time belongs in a test-local fake instead.
"""

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _isolate_forge_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Prevent a developer's real configuration from leaking into tests.

    Any ``FORGE_*`` variable present in the ambient environment is removed for
    the duration of every test, so a test that depends on configuration has to
    set it explicitly.
    """
    for key in [k for k in os.environ if k.startswith("FORGE_")]:
        monkeypatch.delenv(key, raising=False)
    yield
