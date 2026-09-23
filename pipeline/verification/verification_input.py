import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerificationInput:
    """
    Normalized input for semantic verification.
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

    if path is None:
        return {}

    path = Path(path)

    if not path.exists():
        return {}

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            return json.load(handle)

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {}


def _find_json_file(
    outputs_directory,
    filename,
):
    """
    Find one known metadata file.
    """

    path = (
        Path(outputs_directory)
        / filename
    )

    if path.exists():
        return path

    return None


def _extract_manifest_files(
    manifest,
):
    """
    Extract MIGRATE, PRESERVE, and SKIP decisions.
    """

    migrated_files = []
    preserved_files = []
    skipped_files = []

    if not isinstance(
        manifest,
        dict,
    ):
        return (
            migrated_files,
            preserved_files,
            skipped_files,
        )

    for item in manifest.get(
        "files",
        [],
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

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
    dependency_graph,
):
    """
    Extract symbols from dependency metadata.
    """

    if not isinstance(
        dependency_graph,
        dict,
    ):
        return {}

    return dependency_graph.get(
        "symbols",
        dependency_graph.get(
            "file_symbols",
            {},
        ),
    )


def _extract_dependencies(
    dependency_graph,
):
    """
    Extract dependency information.
    """

    if not isinstance(
        dependency_graph,
        dict,
    ):
        return {}

    return dependency_graph.get(
        "dependencies",
        {},
    )


def _extract_tests(
    dependency_graph,
    skipped_files,
):
    """
    Extract existing test metadata.

    Actual test execution is performed by the semantic
    verifier.
    """

    tests = []

    symbols = _extract_symbols(
        dependency_graph
    )

    skipped = set(
        skipped_files
    )

    for file_name, file_symbols in symbols.items():

        normalized_name = str(
            file_name
        ).replace(
            "\\",
            "/",
        )

        if file_name in skipped:
            continue

        if not (
            normalized_name.startswith(
                "test"
            )
            or normalized_name.startswith(
                "tests/"
            )
            or "/tests/" in normalized_name
        ):
            continue

        if not isinstance(
            file_symbols,
            list,
        ):
            continue

        for symbol in file_symbols:

            if not isinstance(
                symbol,
                dict,
            ):
                continue

            if symbol.get(
                "type"
            ) != "function":
                continue

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


def _is_repository(
    path,
):
    """
    Determine whether a path is a usable Python
    repository.

    A repository must contain at least one Python file.
    """

    if not path:
        return False

    path = Path(path)

    if not path.exists():
        return False

    if not path.is_dir():
        return False

    return any(
        path.rglob("*.py")
    )


def _resolve_original_repository(
    manifest,
    outputs_directory,
):
    """
    Resolve the actual original repository.

    The manifest can contain a machine-specific path.

    Resolution order:

    1. Explicit environment override.
    2. Nested repository with the same name as the
       manifest directory.
    3. The manifest directory itself.
    4. Common workspace candidates.
    """

    #
    # Explicit environment override.
    #

    environment_path = os.environ.get(
        "VERIFICATION_ORIGINAL_REPOSITORY"
    )

    if _is_repository(
        environment_path
    ):
        return str(
            Path(
                environment_path
            ).resolve()
        )

    #
    # Manifest path.
    #

    manifest_value = str(
        manifest.get(
            "original_repository",
            "",
        )
    )

    manifest_path = Path(
        manifest_value
    )

    repository_name = (
        manifest_path.name
    )

    #
    # IMPORTANT:
    #
    # The actual test repository is nested:
    #
    # python2_migration_test_repo\
    #     python2_migration_test_repo\
    #         billing.py
    #
    # Therefore check the nested directory BEFORE
    # accepting the outer directory.
    #

    if manifest_path.exists():

        nested_candidate = (
            manifest_path
            / repository_name
        )

        if _is_repository(
            nested_candidate
        ):
            return str(
                nested_candidate.resolve()
            )

    #
    # If the manifest path itself is the repository,
    # use it.
    #

    if _is_repository(
        manifest_path
    ):
        return str(
            manifest_path.resolve()
        )

    #
    # Search common locations.
    #

    outputs_directory = Path(
        outputs_directory
    ).resolve()

    candidates = []

    if repository_name:

        candidates.extend(
            [
                outputs_directory.parent
                / repository_name,

                outputs_directory.parent.parent
                / repository_name,

                Path.home()
                / "Downloads"
                / repository_name,

                Path.home()
                / "OneDrive"
                / "Downloads"
                / repository_name,

                Path.home()
                / "OneDrive"
                / "Documents"
                / repository_name,
            ]
        )

    for candidate in candidates:

        candidate = Path(
            candidate
        )

        #
        # Prefer nested same-name repository.
        #

        nested_candidate = (
            candidate
            / repository_name
        )

        if _is_repository(
            nested_candidate
        ):
            return str(
                nested_candidate.resolve()
            )

        #
        # Otherwise use the candidate itself.
        #

        if _is_repository(
            candidate
        ):
            return str(
                candidate.resolve()
            )

    return ""


def _resolve_migrated_repository(
    manifest,
    outputs_directory,
):
    """
    Resolve the migrated Python 3 repository.

    Resolution order:

    1. Explicit environment override.
    2. Existing manifest path.
    3. Current project's outputs directory.
    """

    #
    # Explicit environment override.
    #

    environment_path = os.environ.get(
        "VERIFICATION_MIGRATED_REPOSITORY"
    )

    if _is_repository(
        environment_path
    ):
        return str(
            Path(
                environment_path
            ).resolve()
        )

    #
    # Existing manifest path.
    #

    manifest_path = Path(
        manifest.get(
            "output_repository",
            "",
        )
    )

    if _is_repository(
        manifest_path
    ):
        return str(
            manifest_path.resolve()
        )

    #
    # Current outputs directory.
    #

    outputs_directory = Path(
        outputs_directory
    ).resolve()

    candidates = [
        outputs_directory
        / "python2_migration_test_repo_migrated",

        outputs_directory.parent
        / "python2_migration_test_repo_migrated",
    ]

    for candidate in candidates:

        if _is_repository(
            candidate
        ):
            return str(
                Path(
                    candidate
                ).resolve()
            )

    return ""


def load_verification_input(
    output_directory,
):
    """
    Load verification metadata from the project's outputs
    directory.

    Example:

        outputs/
            python2_migration_test_repo_assembly_manifest.json
            python2_migration_test_repo_dependency_graph.json
            ...
            python2_migration_test_repo_migrated/
    """

    outputs_directory = Path(
        output_directory
    ).resolve()

    #
    # Metadata files live directly under outputs/.
    #

    manifest_path = _find_json_file(
        outputs_directory,
        "python2_migration_test_repo_assembly_manifest.json",
    )

    dependency_graph_path = _find_json_file(
        outputs_directory,
        "python2_migration_test_repo_dependency_graph.json",
    )

    syntax_path = _find_json_file(
        outputs_directory,
        "python2_migration_test_repo_syntax_verification.json",
    )

    dependency_verification_path = _find_json_file(
        outputs_directory,
        "python2_migration_test_repo_dependency_verification.json",
    )

    migration_results_path = _find_json_file(
        outputs_directory,
        "python2_migration_test_repo_migration_results.json",
    )

    #
    # Load metadata independently.
    #

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

    #
    # Extract migration metadata.
    #

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

    #
    # Resolve repositories.
    #

    original_repository = (
        _resolve_original_repository(
            manifest=manifest,
            outputs_directory=outputs_directory,
        )
    )

    migrated_repository = (
        _resolve_migrated_repository(
            manifest=manifest,
            outputs_directory=outputs_directory,
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