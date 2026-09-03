from __future__ import annotations

import re
from pathlib import PurePosixPath

CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".swift",
    ".ts",
    ".tsx",
}


def normalized(path: str) -> str:
    value = path.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def is_test_path(path: str) -> bool:
    value = normalized(path).lower()
    parts = PurePosixPath(value).parts
    name = parts[-1] if parts else value
    if any(
        part in {"test", "tests", "spec", "specs", "__tests__"} for part in parts[:-1]
    ):
        return True
    if "/src/test/" in f"/{value}/":
        return True
    patterns = (
        r"^test_.+\.py$",
        r".+_test\.py$",
        r".+_test\.go$",
        r".+\.(?:test|spec)\.(?:[cm]?[jt]sx?|py|rb|cs|java|kt|kts|swift)$",
        r".+(?:test|tests|spec|specs)\.(?:rs|cpp?|cc)$",
    )
    return any(re.fullmatch(pattern, name) for pattern in patterns)


def is_ci_path(path: str) -> bool:
    value = normalized(path).lower()
    name = PurePosixPath(value).name
    return (
        value.startswith(".github/workflows/")
        or value == ".gitlab-ci.yml"
        or value == ".gitlab-ci.yaml"
        or value == "azure-pipelines.yml"
        or value.startswith(".circleci/")
        or name == "jenkinsfile"
        or name.startswith("buildkite")
    )


def is_coverage_path(path: str) -> bool:
    value = normalized(path).lower()
    name = PurePosixPath(value).name
    names = {
        ".coveragerc",
        "codecov.yml",
        "codecov.yaml",
        "coverage.json",
        "jest.config.js",
        "jest.config.ts",
        "vitest.config.js",
        "vitest.config.ts",
        "nyc.config.js",
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
        "package.json",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "sonar-project.properties",
    }
    return name in names or name.startswith("coverage.")


def is_command_config_path(path: str) -> bool:
    name = PurePosixPath(normalized(path).lower()).name
    return is_ci_path(path) or name in {
        "package.json",
        "makefile",
        "justfile",
        "taskfile.yml",
        "taskfile.yaml",
        "pyproject.toml",
        "tox.ini",
        "noxfile.py",
    }


def is_snapshot_path(path: str) -> bool:
    value = normalized(path).lower()
    name = PurePosixPath(value).name
    return "__snapshots__" in PurePosixPath(value).parts or name.endswith(
        (".snap", ".golden", ".approved")
    )


def is_code_path(path: str) -> bool:
    return PurePosixPath(normalized(path)).suffix.lower() in CODE_SUFFIXES


def is_relevant_untracked(path: str) -> bool:
    return (
        is_test_path(path)
        or is_ci_path(path)
        or is_coverage_path(path)
        or is_command_config_path(path)
        or is_snapshot_path(path)
    )
