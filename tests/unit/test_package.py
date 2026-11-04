"""Foundation-level checks on the package itself.

These are intentionally boring. Their job is to fail loudly if the packaging,
the entry point, or the layer boundaries are broken by a future change.
"""

import ast
import importlib
import tomllib
from pathlib import Path

import pytest

import forge

LAYERS = [
    "forge.domain",
    "forge.application",
    "forge.infrastructure",
    "forge.presentation",
    "forge.cli",
]

# Layers that must stay free of every framework and SDK, and the packages they
# are not allowed to reach. This mirrors the Ruff TID251 configuration in
# pyproject.toml; see docs/architecture/overview.md.
PURE_LAYERS = ["domain", "application"]
FORBIDDEN_PACKAGES = frozenset(
    {
        "typer",
        "click",
        "rich",
        "openai",
        "httpx",
        "httpx2",
        "git",
        "loguru",
        "pydantic",
    }
)

SRC = Path(forge.__file__).parent
PROJECT_ROOT = SRC.parents[1]


@pytest.mark.unit
def test_package_exposes_a_version() -> None:
    assert isinstance(forge.__version__, str)
    assert forge.__version__


@pytest.mark.unit
def test_distribution_name_and_console_script_are_stable() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert project["name"] == "mntoyg-forge"
    assert project["scripts"]["forge"] == "forge.main:app"


@pytest.mark.unit
@pytest.mark.parametrize("layer", LAYERS)
def test_every_layer_is_importable(layer: str) -> None:
    assert importlib.import_module(layer) is not None


@pytest.mark.unit
@pytest.mark.parametrize("layer", LAYERS)
def test_every_layer_documents_its_contract(layer: str) -> None:
    """A layer package without a docstring has lost its stated boundary."""
    module = importlib.import_module(layer)

    assert module.__doc__, f"{layer} must document its dependency rules"


def _top_level_imports(source: Path) -> set[str]:
    """Return the root package name of every import in a source file."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.unit
@pytest.mark.parametrize("layer", PURE_LAYERS)
def test_inner_layers_import_no_framework(layer: str) -> None:
    """The inner layers must not reach for a framework or an SDK.

    This is the static counterpart to the Ruff TID251 rules in
    ``pyproject.toml``. It reads the source rather than importing it, so it
    catches every import form - including a bare ``import typer`` that leaves
    nothing inspectable in the module namespace.
    """
    offenders: list[str] = []
    for source in sorted((SRC / layer).rglob("*.py")):
        for package in sorted(_top_level_imports(source) & FORBIDDEN_PACKAGES):
            offenders.append(f"{source.relative_to(SRC)} imports {package}")

    assert not offenders, "Dependency direction violated: " + "; ".join(offenders)
