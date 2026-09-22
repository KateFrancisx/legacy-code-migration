"""
Semantic verification input adapter.

Consumes outputs produced by the upstream migration pipeline and exposes
them in one normalized structure for semantic verification.

This module does not perform repository analysis, dependency analysis,
syntax analysis, or migration planning.
"""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class VerificationInputError(Exception):
    """Raised when required verification input is missing or invalid."""


@dataclass
class VerificationInput:
    """Normalized input consumed by semantic verification."""

    original_repository: Optional[str] = None
    migrated_repository: Optional[str] = None

    migrated_files: List[str] = field(default_factory=list)
    preserved_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)

    symbols: Dict[str, Any] = field(default_factory=dict)
    dependencies: Dict[str, Any] = field(default_factory=dict)

    tests: Dict[str, Any] = field(default_factory=dict)

    migration_results: Any = field(default_factory=list)

    syntax_verification: Dict[str, Any] = field(default_factory=dict)
    dependency_verification: Dict[str, Any] = field(default_factory=dict)

    assembly_manifest: Dict[str, Any] = field(default_factory=dict)


def _load_json(path: Path) -> Any:
    """Load JSON while preserving its original structure."""

    if not path.exists():
        raise VerificationInputError(
            "Required verification output was not found: "
            + str(path)
        )

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    except json.JSONDecodeError as exc:
        raise VerificationInputError(
            "Invalid JSON in verification output: "
            + str(path)
            + " - "
            + str(exc)
        ) from exc


def _require_dict(data: Any, path: Path) -> Dict[str, Any]:
    """Require a JSON object."""

    if not isinstance(data, dict):
        raise VerificationInputError(
            "Expected a JSON object in: "
            + str(path)
            + " but found "
            + type(data).__name__
        )

    return data


def _find_first_existing(
    output_directory: Path,
    candidates: List[str],
) -> Path:
    """Return the first existing candidate file."""

    for candidate in candidates:
        path = output_directory / candidate

        if path.exists():
            return path

    raise VerificationInputError(
        "Could not find any of the expected output files: "
        + ", ".join(candidates)
        + " in "
        + str(output_directory)
    )


def _extract_manifest_files(
    manifest: Dict[str, Any],
    decision: str,
) -> List[str]:
    """
    Extract files from the assembly manifest according to decision.

    The actual manifest structure is:

        {
            "files": [
                {
                    "file": "billing.py",
                    "decision": "MIGRATE"
                }
            ]
        }
    """

    files = manifest.get("files", [])

    if not isinstance(files, list):
        return []

    result = []

    for entry in files:
        if not isinstance(entry, dict):
            continue

        if entry.get("decision") != decision:
            continue

        file_path = entry.get("file")

        if file_path:
            result.append(str(file_path))

    return sorted(set(result))


def _extract_symbols(
    dependency_graph: Dict[str, Any],
) -> Dict[str, Any]:
    """Use symbols already produced by the upstream pipeline."""

    symbols = dependency_graph.get("symbols", {})

    if isinstance(symbols, dict):
        return symbols

    return {}


def _extract_dependencies(
    dependency_graph: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Preserve the dependency graph produced upstream.

    No dependency analysis is performed here.
    """

    return {
        "adjacency": dependency_graph.get(
            "adjacency",
            {},
        ),
        "reverse_adjacency": dependency_graph.get(
            "reverse_adjacency",
            {},
        ),
        "edges": dependency_graph.get(
            "edges",
            [],
        ),
        "statistics": dependency_graph.get(
            "statistics",
            {},
        ),
    }


def _extract_tests(
    dependency_graph: Dict[str, Any],
    assembly_manifest: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract test information from the upstream dependency graph
    and assembly manifest.
    """

    test_files = []

    files = dependency_graph.get("files", [])

    if isinstance(files, list):
        for entry in files:
            if not isinstance(entry, dict):
                continue

            if entry.get("is_test") is True:
                path = (
                    entry.get("path")
                    or entry.get("file")
                    or entry.get("relative_path")
                )

                if path:
                    test_files.append(str(path))

    # The dependency graph used by the current pipeline stores test
    # information in symbols as well.
    symbols = dependency_graph.get("symbols", {})

    if isinstance(symbols, dict):
        for path in symbols:
            normalized = str(path).replace("\\", "/")

            if (
                normalized.startswith("tests/")
                or normalized.startswith("test_")
                or normalized.endswith("_test.py")
            ):
                test_files.append(str(path))

    # Also inspect the assembly manifest for skipped tests.
    skipped_files = _extract_manifest_files(
        assembly_manifest,
        "SKIP",
    )

    skipped_test_files = []

    for path in skipped_files:
        normalized = str(path).replace("\\", "/")

        if (
            normalized.startswith("tests/")
            or normalized.startswith("test_")
            or normalized.endswith("_test.py")
        ):
            skipped_test_files.append(path)

    return {
        "test_files": sorted(set(test_files)),
        "skipped_test_files": sorted(
            set(skipped_test_files)
        ),
    }


def load_verification_input(
    output_directory: str,
) -> VerificationInput:
    """
    Load upstream migration outputs for semantic verification.
    """

    output_path = Path(output_directory)

    if not output_path.exists():
        raise VerificationInputError(
            "Output directory does not exist: "
            + str(output_path)
        )

    assembly_path = _find_first_existing(
        output_path,
        [
            "python2_migration_test_repo_assembly_manifest.json",
            "assembly_manifest.json",
        ],
    )

    dependency_graph_path = _find_first_existing(
        output_path,
        [
            "python2_migration_test_repo_dependency_graph.json",
            "dependency_graph.json",
        ],
    )

    syntax_path = _find_first_existing(
        output_path,
        [
            "python2_migration_test_repo_syntax_verification.json",
            "syntax_verification.json",
        ],
    )

    dependency_verification_path = _find_first_existing(
        output_path,
        [
            "python2_migration_test_repo_dependency_verification.json",
            "dependency_verification.json",
        ],
    )

    migration_results_path = _find_first_existing(
        output_path,
        [
            "python2_migration_test_repo_migration_results.json",
            "migration_results.json",
        ],
    )

    assembly_manifest = _require_dict(
        _load_json(assembly_path),
        assembly_path,
    )

    dependency_graph = _require_dict(
        _load_json(dependency_graph_path),
        dependency_graph_path,
    )

    syntax_verification = _require_dict(
        _load_json(syntax_path),
        syntax_path,
    )

    dependency_verification = _require_dict(
        _load_json(dependency_verification_path),
        dependency_verification_path,
    )

    # Migration results are currently a JSON list containing one
    # record per migrated source file.
    migration_results = _load_json(
        migration_results_path
    )

    if not isinstance(
        migration_results,
        (list, dict),
    ):
        raise VerificationInputError(
            "Migration results must be a JSON list or object: "
            + str(migration_results_path)
        )

    original_repository = (
        assembly_manifest.get(
            "original_repository"
        )
    )

    migrated_repository = (
        assembly_manifest.get(
            "output_repository"
        )
    )

    migrated_files = _extract_manifest_files(
        assembly_manifest,
        "MIGRATE",
    )

    preserved_files = _extract_manifest_files(
        assembly_manifest,
        "PRESERVE",
    )

    skipped_files = _extract_manifest_files(
        assembly_manifest,
        "SKIP",
    )

    symbols = _extract_symbols(
        dependency_graph
    )

    dependencies = _extract_dependencies(
        dependency_graph
    )

    tests = _extract_tests(
        dependency_graph,
        assembly_manifest,
    )

    return VerificationInput(
        original_repository=original_repository,
        migrated_repository=migrated_repository,
        migrated_files=migrated_files,
        preserved_files=preserved_files,
        skipped_files=skipped_files,
        symbols=symbols,
        dependencies=dependencies,
        tests=tests,
        migration_results=migration_results,
        syntax_verification=syntax_verification,
        dependency_verification=dependency_verification,
        assembly_manifest=assembly_manifest,
    )


def print_verification_input_summary(
    verification_input: VerificationInput,
) -> None:
    """Print a compact verification-input summary."""

    print("Semantic Verification Input")
    print("=" * 32)

    print(
        "Original repository: "
        + str(
            verification_input.original_repository
        )
    )

    print(
        "Migrated repository: "
        + str(
            verification_input.migrated_repository
        )
    )

    print(
        "Migrated files: "
        + str(
            len(
                verification_input.migrated_files
            )
        )
    )

    if verification_input.migrated_files:
        for path in verification_input.migrated_files:
            print("  MIGRATE: " + path)

    print(
        "Preserved files: "
        + str(
            len(
                verification_input.preserved_files
            )
        )
    )

    if verification_input.preserved_files:
        for path in verification_input.preserved_files:
            print("  PRESERVE: " + path)

    print(
        "Skipped files: "
        + str(
            len(
                verification_input.skipped_files
            )
        )
    )

    if verification_input.skipped_files:
        for path in verification_input.skipped_files:
            print("  SKIP: " + path)

    print(
        "Symbol files: "
        + str(
            len(
                verification_input.symbols
            )
        )
    )

    print(
        "Dependency edges: "
        + str(
            len(
                verification_input.dependencies.get(
                    "edges",
                    [],
                )
            )
        )
    )

    print(
        "Test files: "
        + str(
            len(
                verification_input.tests.get(
                    "test_files",
                    [],
                )
            )
        )
    )

    migration_results = (
        verification_input.migration_results
    )

    if isinstance(
        migration_results,
        list,
    ):
        print(
            "Migration results: "
            + str(
                len(migration_results)
            )
            + " records"
        )

    elif isinstance(
        migration_results,
        dict,
    ):
        print(
            "Migration results: "
            + str(
                len(migration_results)
            )
            + " fields"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Load migration pipeline outputs "
            "for semantic verification."
        )
    )

    parser.add_argument(
        "output_directory",
        help=(
            "Directory containing migration "
            "outputs."
        ),
    )

    args = parser.parse_args()

    verification_input = (
        load_verification_input(
            args.output_directory
        )
    )

    print_verification_input_summary(
        verification_input
    )


if __name__ == "__main__":
    main()