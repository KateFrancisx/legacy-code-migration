from pathlib import Path


def discover_test_files(repo_path):
    """
    Discover Python test files in a repository.

    Supported patterns:
        tests/**/*.py
        test_*.py
        *_test.py

    Returns:
        list[str]: Sorted list of test file paths.
    """

    repo_path = Path(repo_path)

    if not repo_path.exists():
        raise FileNotFoundError(
            f"Repository not found: {repo_path}"
        )

    if not repo_path.is_dir():
        raise NotADirectoryError(
            f"Repository path is not a directory: {repo_path}"
        )

    test_files = set()

    # 1. tests/ directory
    tests_dir = repo_path / "tests"

    if tests_dir.exists() and tests_dir.is_dir():
        for path in tests_dir.rglob("*.py"):
            if path.is_file():
                test_files.add(path)

    # 2. test_*.py anywhere in repository
    for path in repo_path.rglob("test_*.py"):
        if path.is_file():
            test_files.add(path)

    # 3. *_test.py anywhere in repository
    for path in repo_path.rglob("*_test.py"):
        if path.is_file():
            test_files.add(path)

    return sorted(
        str(path)
        for path in test_files
    )


def detect_test_framework(repo_path, test_files=None):
    """
    Detect the test framework used by the repository.

    Detection is based on:
        - requirements files
        - pyproject.toml
        - setup.cfg
        - tox.ini
        - test source code

    Returns:
        str:
            "pytest"
            "unittest"
            "unknown"
            "none"
    """

    repo_path = Path(repo_path)

    if test_files is None:
        test_files = discover_test_files(repo_path)

    # No tests discovered.
    if not test_files:
        return "none"

    # Read common project configuration files.
    config_files = [
        repo_path / "requirements.txt",
        repo_path / "requirements-dev.txt",
        repo_path / "requirements-test.txt",
        repo_path / "pyproject.toml",
        repo_path / "setup.cfg",
        repo_path / "tox.ini",
    ]

    config_text = ""

    for config_file in config_files:
        if config_file.exists() and config_file.is_file():
            try:
                config_text += "\n" + config_file.read_text(
                    encoding="utf-8",
                    errors="ignore"
                ).lower()
            except OSError:
                pass

    # Pytest configuration/dependency.
    if (
        "pytest" in config_text
        or "[tool.pytest" in config_text
        or "[pytest]" in config_text
    ):
        return "pytest"

    # Inspect test source files.
    unittest_found = False
    pytest_found = False

    for test_file in test_files:
        try:
            source = Path(test_file).read_text(
                encoding="utf-8",
                errors="ignore"
            )
        except OSError:
            continue

        source_lower = source.lower()

        # Pytest indicators.
        if (
            "import pytest" in source_lower
            or "from pytest" in source_lower
            or "@pytest." in source_lower
        ):
            pytest_found = True

        # unittest indicators.
        if (
            "import unittest" in source_lower
            or "from unittest" in source_lower
            or "unittest.testcase" in source_lower
        ):
            unittest_found = True

    # If both appear, prefer pytest because pytest can execute
    # unittest-based tests as well.
    if pytest_found:
        return "pytest"

    if unittest_found:
        return "unittest"

    return "unknown"


def discover_tests(repo_path):
    """
    Backward-compatible helper.

    Returns only the discovered test file paths.

    This preserves the API used by earlier verification code.
    """

    return discover_test_files(repo_path)


def discover_test_suite(repo_path):
    """
    Discover the complete test configuration for a repository.

    Returns:
        {
            "repository": "...",
            "test_files": [...],
            "test_count": 0,
            "framework": "pytest"
        }
    """

    test_files = discover_test_files(repo_path)

    framework = detect_test_framework(
        repo_path,
        test_files
    )

    return {
        "repository": str(Path(repo_path)),
        "test_files": test_files,
        "test_count": len(test_files),
        "framework": framework,
    }