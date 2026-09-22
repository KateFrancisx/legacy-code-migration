import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerificationInput:
    """
    Normalized input for the semantic verification stage.

    Paths from upstream manifests are treated as metadata.
    The actual repository locations are resolved from the
    current verification workspace.
    """

    original_repository: str
    migrated_repository: str

    migrated_files: list = field(
        default_factory=list
    )

    preserved_files: list = field(
        default_factory=list
    )

    skipped_files: list = field(
        default_factory=list
    )

    symbols: dict = field(
        default_factory=dict
    )

    dependencies: dict = field(
        default_factory=dict
    )

    tests: list = field(
        default_factory=list
    )

    migration_results: dict = field(
        default_factory=dict
    )

    syntax_verification: dict = field(
        default_factory=dict
    )

    dependency_verification: dict = field(
        default_factory=dict
    )

    assembly_manifest: dict = field(
        default_factory=dict
    )


def _load_json(path):
    """
    Load a JSON file.
    """

    if not path.exists():
        return {}

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def _find_repository_from_manifest(
    manifest,
    output_directory,
):
    """
    Resolve the original repository using the current
    workspace rather than trusting a machine-specific
    path stored in the manifest.

    Resolution order:

    1. Explicit repository path supplied through the
       output directory's parent workspace.
    2. Manifest path if it still exists.
    3. A sibling repository matching the migrated
       repository name.
    """

    manifest_path = Path(
        manifest.get(
            "original_repository",
            "",
        )
    )

    if manifest_path.exists():
        return str(
            manifest_path.resolve()
        )

    output_path = Path(
        output_directory
    ).resolve()

    migrated_repository = Path(
        manifest.get(
            "output_repository",
            "",
        )
    )

    if migrated_repository.exists():
        migrated_repository = (
            migrated_repository.resolve()
        )
    else:
        migrated_repository = (
            output_path
            / f"{output_path.name}_migrated"
        )

    # The test workspace used by the local migration
    # pipeline has the original repository alongside
    # the migrated output when both are available.
    candidates = [
        output_path.parent
        / "python2_migration_test_repo",

        output_path.parent
        / output_path.name,

        output_path.parent
        / (
            output_path.name
            .replace(
                "_migrated",
                "",
            )
        ),
    ]

    for candidate in candidates:
        candidate = candidate.resolve()

        if candidate.exists() and candidate.is_dir():
            return str(candidate)

    # If the manifest path is stale, keep it as metadata
    # rather than silently inventing a different location.
    return str(
        manifest_path
    )


def _resolve_migrated_repository(
    manifest,
    output_directory,
):
    """
    Resolve the migrated repository.

    Prefer the manifest path when it exists.

    Otherwise, resolve the migrated repository relative
    to the current output directory.
    """

    manifest_path = Path(
        manifest.get(
            "output_repository",
            "",
        )
    )

    if manifest_path.exists():
        return str(
            manifest_path.resolve()
        )

    output_path = Path(
        output_directory
    ).resolve()

    candidates = [
        output_path
        / f"{output_path.name}_migrated",

        output_path.parent
        / f"{output_path.name}_migrated",
    ]

    for candidate in candidates:
        candidate = candidate.resolve()

        if candidate.exists() and candidate.is_dir():
            return str(candidate)

    return str(
        manifest_path
    )


def _extract_manifest_files(
    manifest
):
    """
    Extract file decisions from the assembly manifest.
    """

    migrated_files = []
    preserved_files = []
    skipped_files = []

    for item in manifest.get(
        "files",
        [],
    ):
        file_name = item.get(
            "file"
        )

        decision = str(
            item.get(
                "decision",
                "",
            )
        ).upper()

        if not file_name:
            continue

        if decision == "MIGRATE":
            migrated_files.append(
                file_name
            )

        elif decision == "PRESERVE":
            preserved_files.append(
                file_name
            )

        elif decision == "SKIP":
            skipped_files.append(
                file_name
            )

    return (
        migrated_files,
        preserved_files,
        skipped_files,
    )


def _extract_symbols(
    dependency_graph
):
    """
    Extract symbol information from the dependency graph.
    """

    return dependency_graph.get(
        "symbols",
        dependency_graph.get(
            "file_symbols",
            {},
        ),
    )


def _extract_dependencies(
    dependency_graph
):
    """
    Extract dependency information from the dependency graph.
    """

    return dependency_graph.get(
        "dependencies",
        {},
    )


def _extract_tests(
    dependency_graph,
    skipped_files,
):
    """
    Extract existing test information.
    """

    tests = []

    symbols = dependency_graph.get(
        "symbols",
        {},
    )

    for file_name, file_symbols in symbols.items():

        if file_name in skipped_files:
            continue

        if not (
            file_name.startswith(
                "test"
            )
            or "/tests/" in file_name.replace(
                "\\",
                "/",
            )
            or file_name.replace(
                "\\",
                "/",
            ).startswith(
                "tests/"
            )
        ):
            continue

        for symbol in file_symbols:
            if symbol.get(
                "type"
            ) == "function":
                tests.append(
                    {
                        "file": file_name,
                        "name": symbol.get(
                            "name"
                        ),
                        "line": symbol.get(
                            "line"
                        ),
                    }
                )

    return tests


def load_verification_input(
    output_directory
):
    """
    Load all upstream migration-analysis outputs.

    The upstream outputs provide analysis metadata.

    Repository paths are resolved for the current
    machine/workspace instead of blindly trusting paths
    recorded on another machine.
    """

    output_path = Path(
        output_directory
    ).resolve()

    manifest_path = (
        output_path
        / "python2_migration_test_repo_assembly_manifest.json"
    )

    dependency_graph_path = (
        output_path
        / "python2_migration_test_repo_dependency_graph.json"
    )

    syntax_path = (
        output_path
        / "python2_migration_test_repo_syntax_verification.json"
    )

    dependency_verification_path = (
        output_path
        / "python2_migration_test_repo_dependency_verification.json"
    )

    migration_results_path = (
        output_path
        / "python2_migration_test_repo_migration_results.json"
    )

    manifest = _load_json(
        manifest_path
    )

    dependency_graph = _load_json(
        dependency_graph_path
    )

    syntax_verification = _load_json(
        syntax_path
    )

    dependency_verification = _load_json(
        dependency_verification_path
    )

    migration_results = _load_json(
        migration_results_path
    )

    (
        migrated_files,
        preserved_files,
        skipped_files,
    ) = _extract_manifest_files(
        manifest
    )

    symbols = _extract_symbols(
        dependency_graph
    )

    dependencies = _extract_dependencies(
        dependency_graph
    )

    tests = _extract_tests(
        dependency_graph,
        skipped_files,
    )

    original_repository = (
        _find_repository_from_manifest(
            manifest,
            output_path,
        )
    )

    migrated_repository = (
        _resolve_migrated_repository(
            manifest,
            output_path,
        )
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
        assembly_manifest=manifest,
    )