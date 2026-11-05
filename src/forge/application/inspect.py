"""Build a concise overview from bounded project evidence."""

import json
import re
import tomllib
from pathlib import Path

from forge.domain.errors import SourceNotFoundError, SourceUnreadableError
from forge.domain.project import (
    ProjectEvidenceReader,
    ProjectFact,
    ProjectOmission,
    ProjectOmissionCode,
    ProjectOverview,
)

_GUIDANCE = frozenset(
    {"AGENTS.md", "CLAUDE.md", ".cursorrules", "CONTRIBUTING.md", "README.md"}
)
_LANGUAGES = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".sh": "Shell",
    ".sql": "SQL",
}
_TOOL_CONFIGS = {
    "pyproject.toml": "Python project metadata",
    "package.json": "Node.js package metadata",
    "Cargo.toml": "Cargo project metadata",
    "go.mod": "Go module metadata",
    "pom.xml": "Maven project metadata",
    "build.gradle": "Gradle project metadata",
    "build.gradle.kts": "Gradle Kotlin project metadata",
    "requirements.txt": "Python requirements file",
    "tox.ini": "tox configuration",
    "pytest.ini": "pytest configuration",
    "ruff.toml": "Ruff configuration",
    ".ruff.toml": "Ruff configuration",
    "Makefile": "Make targets",
    "justfile": "just recipes",
}


class InspectProject:
    """Return facts supported by selected project files and visible structure."""

    def __init__(self, reader: ProjectEvidenceReader) -> None:
        self._reader = reader

    def __call__(self, root: Path) -> ProjectOverview:
        """Inspect one directory without executing or modifying project data."""
        try:
            resolved = root.resolve(strict=True)
        except FileNotFoundError as error:
            raise SourceNotFoundError(
                f"No such directory: {root}. Provide an existing project directory."
            ) from error
        except (OSError, RuntimeError) as error:
            raise SourceUnreadableError(f"Cannot access directory: {root}") from error
        if not resolved.is_dir():
            raise SourceUnreadableError(
                f"{root} is not a directory. Give the path to a project directory."
            )

        evidence = self._reader.collect(resolved)
        paths = set(evidence.file_paths)
        contents = {item.path: item.content for item in evidence.files}

        guidance = tuple(
            sorted(
                path
                for path in paths
                if Path(path).name in _GUIDANCE
                or path.startswith(
                    (".forge/agents/", ".forge/context/", ".forge/workflows/")
                )
                or path == ".forge/NEXT_PROMPT.md"
                or path == ".github/copilot-instructions.md"
                or path.startswith(".github/instructions/")
            )
        )
        languages = _languages(paths)
        tooling = _tooling(paths, contents)
        checks = _checks(paths, contents)

        omissions = [
            "Ignore filtering uses project .gitignore rules and built-in exclusions; Git info/global excludes are not consulted.",
            *evidence.omissions,
        ]
        structured_omissions = [
            ProjectOmission(ProjectOmissionCode.GIT_GLOBAL_EXCLUDES_NOT_CONSULTED),
            *evidence.structured_omissions,
        ]
        if not any(Path(path).name in _TOOL_CONFIGS for path in paths):
            checked = ", ".join(sorted(_TOOL_CONFIGS))
            omissions.append(
                f"No supported project metadata file was found; checked: {checked}."
            )
            structured_omissions.append(
                ProjectOmission(ProjectOmissionCode.NO_SUPPORTED_METADATA)
            )
        if not evidence.complete:
            omissions.append("The project scan stopped at a safety limit.")

        return ProjectOverview(
            root=evidence.root,
            guidance=guidance,
            languages=languages,
            tooling=tooling,
            checks=checks,
            directories=evidence.directories,
            omissions=tuple(dict.fromkeys(omissions)),
            scan_complete=evidence.complete,
            structured_omissions=tuple(dict.fromkeys(structured_omissions)),
        )


def _languages(paths: set[str]) -> tuple[ProjectFact, ...]:
    evidence: dict[str, set[str]] = {}
    for path in paths:
        language = _LANGUAGES.get(Path(path).suffix.lower())
        if language is not None:
            evidence.setdefault(language, set()).add(path)
    return tuple(
        ProjectFact(name, tuple(sorted(sources)))
        for name, sources in sorted(evidence.items())
    )


def _tooling(paths: set[str], contents: dict[str, str]) -> tuple[ProjectFact, ...]:
    evidence: dict[str, set[str]] = {}
    for path in paths:
        name = Path(path).name
        label = _TOOL_CONFIGS.get(name)
        if label is not None:
            evidence.setdefault(label, set()).add(path)

    pyproject = next(
        (
            text
            for path, text in contents.items()
            if Path(path).name == "pyproject.toml"
        ),
        None,
    )
    if pyproject is not None:
        try:
            metadata = tomllib.loads(pyproject)
        except tomllib.TOMLDecodeError:
            evidence.setdefault("Malformed pyproject.toml", set()).add(
                next(path for path in contents if Path(path).name == "pyproject.toml")
            )
        else:
            tools = metadata.get("tool", {})
            if isinstance(tools, dict):
                for tool in ("pytest", "ruff", "black", "mypy"):
                    if tool in tools:
                        evidence.setdefault(f"{tool} configuration", set()).add(
                            next(
                                path
                                for path in contents
                                if Path(path).name == "pyproject.toml"
                            )
                        )

    package_json = next(
        (text for path, text in contents.items() if Path(path).name == "package.json"),
        None,
    )
    if package_json is not None:
        try:
            package = json.loads(package_json)
        except (json.JSONDecodeError, TypeError):
            evidence.setdefault("Malformed package.json", set()).add(
                next(path for path in contents if Path(path).name == "package.json")
            )
        else:
            if isinstance(package, dict):
                dependencies: set[str] = set()
                for field in ("dependencies", "devDependencies"):
                    values = package.get(field, {})
                    if isinstance(values, dict):
                        dependencies.update(values)
                for package_name, label in {
                    "react": "React",
                    "vue": "Vue",
                    "@angular/core": "Angular",
                    "svelte": "Svelte",
                    "next": "Next.js",
                }.items():
                    if package_name in dependencies:
                        evidence.setdefault(f"{label} dependency", set()).add(
                            next(
                                path
                                for path in contents
                                if Path(path).name == "package.json"
                            )
                        )

    if "uv.lock" in paths:
        evidence.setdefault("uv lockfile", set()).add("uv.lock")
    return tuple(
        ProjectFact(name, tuple(sorted(sources)))
        for name, sources in sorted(evidence.items())
    )


def _checks(paths: set[str], contents: dict[str, str]) -> tuple[ProjectFact, ...]:
    checks: dict[str, set[str]] = {}
    if "scripts/check.py" in paths:
        command = (
            "uv run python scripts/check.py"
            if "uv.lock" in paths
            else "python scripts/check.py"
        )
        checks.setdefault(command, set()).add("scripts/check.py")
    has_pytest = "pytest.ini" in paths
    if "pyproject.toml" in contents:
        try:
            project = tomllib.loads(contents["pyproject.toml"])
        except tomllib.TOMLDecodeError:
            project = {}
        tools = project.get("tool", {})
        has_pytest = has_pytest or (isinstance(tools, dict) and "pytest" in tools)
    if has_pytest:
        command = "uv run pytest" if "uv.lock" in paths else "pytest"
        evidence = "pyproject.toml" if "pyproject.toml" in paths else "pytest.ini"
        checks.setdefault(command, set()).add(evidence)
    if "go.mod" in paths:
        checks.setdefault("go test ./...", set()).add("go.mod")
    if "Cargo.toml" in paths:
        checks.setdefault("cargo test", set()).add("Cargo.toml")
    if "package.json" in contents:
        try:
            package = json.loads(contents["package.json"])
        except (json.JSONDecodeError, TypeError):
            package = None
        if isinstance(package, dict) and isinstance(package.get("scripts"), dict):
            for script in ("test", "lint", "typecheck"):
                if script in package["scripts"]:
                    checks.setdefault(f"npm run {script}", set()).add("package.json")
    if "Makefile" in paths and "Makefile" in contents:
        targets = set(re.findall(r"^([A-Za-z0-9_.-]+):", contents["Makefile"], re.M))
        for target in ("test", "lint", "check"):
            if target in targets:
                checks.setdefault(f"make {target}", set()).add("Makefile")
    return tuple(
        ProjectFact(name, tuple(sorted(sources)))
        for name, sources in sorted(checks.items())
    )
