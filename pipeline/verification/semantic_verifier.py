from .test_discovery import discover_test_suite
from .executor import run_tests
from .comparator import compare_results


def run_repository_tests(
    repo_path,
    python_executable,
    timeout=60,
):
    """
    Discover the repository's tests and execute them.

    The test framework is detected automatically, so this
    function does not assume pytest or unittest.
    """

    test_suite = discover_test_suite(repo_path)

    execution_result = run_tests(
        repo_path=repo_path,
        framework=test_suite["framework"],
        python_executable=python_executable,
        timeout=timeout,
    )

    return {
        "suite": test_suite,
        "execution": execution_result,
    }


def verify_existing_tests(
    original_repo,
    migrated_repo,
    original_python=("py", "-2"),
    migrated_python=("py", "-3"),
    timeout=60,
):
    """
    Compare existing repository tests between the original
    and migrated repositories.

    The original and migrated repositories may use different
    Python runtimes.

    Example:

        original_python=("py", "-2")
        migrated_python=("py", "-3")
    """

    original = run_repository_tests(
        repo_path=original_repo,
        python_executable=original_python,
        timeout=timeout,
    )

    migrated = run_repository_tests(
        repo_path=migrated_repo,
        python_executable=migrated_python,
        timeout=timeout,
    )

    original_execution = original["execution"]
    migrated_execution = migrated["execution"]

    comparison = compare_results(
        original_execution,
        migrated_execution,
    )

    return {
        "original_repository": str(original_repo),
        "migrated_repository": str(migrated_repo),

        "original": {
            "test_suite": original["suite"],
            "execution": original_execution.to_dict(),
        },

        "migrated": {
            "test_suite": migrated["suite"],
            "execution": migrated_execution.to_dict(),
        },

        "comparison": comparison,

        "status": (
            "PASS"
            if comparison["equivalent"]
            else "DIFFERENCE"
        ),
    }


def verify_semantics(
    original_repo,
    migrated_repo,
    original_python=("py", "-2"),
    migrated_python=("py", "-3"),
    timeout=60,
):
    """
    Perform repository-level semantic verification.

    Verification currently compares the behavior of the
    repositories under their existing test suites.

    The implementation is intentionally repository-agnostic:
        - no filename is hardcoded
        - no function is hardcoded
        - no test name is hardcoded
        - the test framework is detected automatically
        - original and migrated Python runtimes are independent

    Returns:
        dict containing:
            - discovered tests
            - detected frameworks
            - execution results
            - behavioral comparison
            - overall verification status
    """

    original_suite = discover_test_suite(
        original_repo
    )

    migrated_suite = discover_test_suite(
        migrated_repo
    )

    result = {
        "original_repository": str(original_repo),
        "migrated_repository": str(migrated_repo),

        "original_tests": original_suite,
        "migrated_tests": migrated_suite,

        "status": "UNKNOWN",
        "test_execution": None,
    }

    # If neither repository contains tests, there is no
    # existing-test evidence with which to establish equivalence.
    if (
        original_suite["framework"] == "none"
        and migrated_suite["framework"] == "none"
    ):
        result["status"] = "NO_TESTS"
        result["test_execution"] = {
            "message": (
                "No existing tests were discovered in either "
                "repository."
            )
        }

        return result

    # If only one repository has tests, the migration cannot
    # be considered equivalent based on existing tests alone.
    if original_suite["framework"] == "none":
        result["status"] = "ORIGINAL_NO_TESTS"
        result["test_execution"] = {
            "message": (
                "The original repository has no discovered "
                "tests."
            )
        }

        return result

    if migrated_suite["framework"] == "none":
        result["status"] = "MIGRATED_NO_TESTS"
        result["test_execution"] = {
            "message": (
                "The migrated repository has no discovered "
                "tests."
            )
        }

        return result

    # Run original repository using Python 2.
    original_execution = run_tests(
        repo_path=original_repo,
        framework=original_suite["framework"],
        python_executable=original_python,
        timeout=timeout,
    )

    # Run migrated repository using Python 3.
    migrated_execution = run_tests(
        repo_path=migrated_repo,
        framework=migrated_suite["framework"],
        python_executable=migrated_python,
        timeout=timeout,
    )

    comparison = compare_results(
        original_execution,
        migrated_execution,
    )

    result["test_execution"] = {
        "original": {
            "runtime": list(original_python),
            "framework": original_suite["framework"],
            "result": original_execution.to_dict(),
        },

        "migrated": {
            "runtime": list(migrated_python),
            "framework": migrated_suite["framework"],
            "result": migrated_execution.to_dict(),
        },

        "comparison": comparison,
    }

    if comparison["equivalent"]:
        result["status"] = "PASS"
    else:
        result["status"] = "DIFFERENCE"

    return result