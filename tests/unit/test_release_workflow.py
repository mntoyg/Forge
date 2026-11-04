"""Guard release distribution and job permission boundaries."""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release.yml"


def _job(name: str) -> str:
    """Return one top-level job block from the release workflow."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-z0-9-]+:\n|\Z)",
        workflow,
    )

    assert match is not None, f"release workflow is missing the {name} job"
    return match.group(1)


@pytest.mark.unit
def test_release_jobs_reuse_the_built_distribution_artifact() -> None:
    build = _job("build")
    github_release = _job("github-release")
    pypi_publish = _job("pypi-publish")

    assert "run: uv build" in build
    assert "name: release-distributions" in build
    assert "needs: build" in github_release
    assert "needs: build" in pypi_publish
    assert "name: release-distributions" in github_release
    assert "name: release-distributions" in pypi_publish


@pytest.mark.unit
def test_release_jobs_limit_write_permissions_to_their_purpose() -> None:
    github_release = _job("github-release")
    pypi_publish = _job("pypi-publish")

    assert "contents: write" in github_release
    assert "id-token: write" not in github_release
    assert "id-token: write" in pypi_publish
    assert "contents: write" not in pypi_publish
    assert "name: pypi" in pypi_publish
    assert re.search(r"pypa/gh-action-pypi-publish@[0-9a-f]{40}", pypi_publish)
