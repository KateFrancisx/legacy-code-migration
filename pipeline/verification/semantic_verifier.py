import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline.verification.differential_executor import (
    execute_function,
)
from pipeline.verification.result_normalizer import (
    normalize_result,
)
from pipeline.verification.test_discovery import (
    discover_test_suite,
)
from pipeline.verification.test_generator import (
    generate_llm_cases_for_functions,
)
from pipeline.verification.verification_input import (
    load_verification_input,
)


@dataclass
class RepositoryTestResult:
    """
    Result of running an existing repository test suite.
    """

    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def compare_results(original, migrated):
    """
    Compare repository test results or function execution results.

    Repository test suites are compared by actual success/failure
    status rather than unittest's textual output.

    Function execution results are compared semantically.
    """

    if (
        hasattr(original, "return_value")
        and hasattr(migrated, "return_value")
    ):
        return _compare_function_results(
            original,
            migrated,
        )

    original_normalized = normalize_result(
        original
    )

    migrated_normalized = normalize_result(
        migrated
    )

    original_success = (
        original.return_code == 0
        and not original.timed_out
    )

    migrated_success = (
        migrated.return_code == 0
        and not migrated.timed_out
    )

    return {
        "equivalent": (
            original_success
            == migrated_success
        ),
        "original": original_normalized,
        "migrated": migrated_normalized,
    }


def _values_semantically_equal(
    original,
    migrated,
):
    """
    Compare values while allowing legitimate Python 2/3
    representation differences such as 10 vs 10.0.
    """

    if (
        isinstance(original, bool)
        or isinstance(migrated, bool)
    ):
        return (
            type(original) is type(migrated)
            and original == migrated
        )

    numeric_types = (
        int,
        float,
    )

    if (
        isinstance(original, numeric_types)
        and isinstance(migrated, numeric_types)
    ):
        return original == migrated

    if type(original) is not type(migrated):
        return False

    if isinstance(original, list):
        return (
            len(original)
            == len(migrated)
            and all(
                _values_semantically_equal(
                    left,
                    right,
                )
                for left, right in zip(
                    original,
                    migrated,
                )
            )
        )

    if isinstance(original, tuple):
        return (
            len(original)
            == len(migrated)
            and all(
                _values_semantically_equal(
                    left,
                    right,
                )
                for left, right in zip(
                    original,
                    migrated,
                )
            )
        )

    if isinstance(original, dict):
        if (
            set(original.keys())
            != set(migrated.keys())
        ):
            return False

        return all(
            _values_semantically_equal(
                original[key],
                migrated[key],
            )
            for key in original
        )

    if isinstance(original, set):
        return original == migrated

    return original == migrated


def _compare_function_results(
    original,
    migrated,
):
    """
    Compare FunctionExecutionResult objects.
    """

    differences = {}
    semantic_differences = {}

    if original.status != migrated.status:
        differences["status"] = {
            "original": original.status,
            "migrated": migrated.status,
            "semantic_difference": True,
        }

        semantic_differences["status"] = {
            "original": original.status,
            "migrated": migrated.status,
        }

    if not _values_semantically_equal(
        original.return_value,
        migrated.return_value,
    ):
        differences["return_value"] = {
            "original": original.return_value,
            "migrated": migrated.return_value,
            "semantic_difference": True,
        }

        semantic_differences["return_value"] = {
            "original": original.return_value,
            "migrated": migrated.return_value,
        }

    if original.return_type != migrated.return_type:
        differences["return_type"] = {
            "original": original.return_type,
            "migrated": migrated.return_type,
            "semantic_difference": False,
        }

    if original.stdout != migrated.stdout:
        differences["stdout"] = {
            "original": original.stdout,
            "migrated": migrated.stdout,
            "semantic_difference": True,
        }

        semantic_differences["stdout"] = {
            "original": original.stdout,
            "migrated": migrated.stdout,
        }

    if original.stderr != migrated.stderr:
        differences["stderr"] = {
            "original": original.stderr,
            "migrated": migrated.stderr,
            "semantic_difference": True,
        }

        semantic_differences["stderr"] = {
            "original": original.stderr,
            "migrated": migrated.stderr,
        }

    if original.exception_type != migrated.exception_type:
        differences["exception_type"] = {
            "original": original.exception_type,
            "migrated": migrated.exception_type,
            "semantic_difference": True,
        }

        semantic_differences["exception_type"] = {
            "original": original.exception_type,
            "migrated": migrated.exception_type,
        }

    if (
        original.exception_message
        != migrated.exception_message
    ):
        differences["exception_message"] = {
            "original": original.exception_message,
            "migrated": migrated.exception_message,
            "semantic_difference": True,
        }

        semantic_differences["exception_message"] = {
            "original": original.exception_message,
            "migrated": migrated.exception_message,
        }

    if original.timed_out != migrated.timed_out:
        differences["timed_out"] = {
            "original": original.timed_out,
            "migrated": migrated.timed_out,
            "semantic_difference": True,
        }

        semantic_differences["timed_out"] = {
            "original": original.timed_out,
            "migrated": migrated.timed_out,
        }

    return {
        "equivalent": (
            len(semantic_differences) == 0
        ),
        "differences": differences,
        "semantic_differences": (
            semantic_differences
        ),
    }


def _run_test_suite(
    repository_path,
    python_executable,
):
    """
    Discover and execute the repository's existing
    unittest test suite.
    """

    discovery = discover_test_suite(
        repository_path
    )

    test_files = discovery.get(
        "test_files",
        [],
    )

    if not test_files:
        return RepositoryTestResult(
            return_code=0,
            stdout="",
            stderr="",
            timed_out=False,
        )

    command = [
        python_executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test*.py",
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

        return RepositoryTestResult(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )

    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout
            if exc.stdout is not None
            else ""
        )

        stderr = (
            exc.stderr
            if exc.stderr is not None
            else ""
        )

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                errors="replace"
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                errors="replace"
            )

        return RepositoryTestResult(
            return_code=-1,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )


def run_tests(
    repository_path,
    python_executable,
):
    """
    Run the discovered repository test suite.
    """

    return _run_test_suite(
        repository_path,
        python_executable,
    )


def run_repository_tests(
    original_repository,
    migrated_repository,
    original_python,
    migrated_python,
):
    """
    Run existing tests under Python 2 and Python 3.
    """

    original_result = run_tests(
        original_repository,
        original_python,
    )

    migrated_result = run_tests(
        migrated_repository,
        migrated_python,
    )

    comparison = compare_results(
        original_result,
        migrated_result,
    )

    return {
        "original": original_result,
        "migrated": migrated_result,
        "comparison": comparison,
    }


def run_differential_test(
    original_repository,
    migrated_repository,
    module_path,
    function_name,
    inputs,
    original_python=r"C:\Python27\python.exe",
    migrated_python=r"py",
):
    """
    Execute one function in both repositories.

    module_path is the path to the migrated module.

    The relative path of that module inside the migrated
    repository is calculated and used to locate the
    corresponding original Python 2 module.

    Example:

        migrated:
            D:\\project\\migrated\\utils.py

        original:
            C:\\project\\original\\utils.py
    """

    original_repository = os.path.abspath(
        original_repository
    )

    migrated_repository = os.path.abspath(
        migrated_repository
    )

    migrated_module_path = os.path.abspath(
        module_path
    )

    try:
        relative_module_path = os.path.relpath(
            migrated_module_path,
            migrated_repository,
        )
    except ValueError:
        return {
            "function": function_name,
            "inputs": inputs,
            "original": None,
            "migrated": None,
            "comparison": {
                "equivalent": False,
                "differences": {
                    "module_path": {
                        "original": original_repository,
                        "migrated": migrated_repository,
                        "semantic_difference": True,
                    }
                },
                "semantic_differences": {
                    "module_path": {
                        "original": original_repository,
                        "migrated": migrated_repository,
                    }
                },
            },
        }

    original_module_path = os.path.abspath(
        os.path.join(
            original_repository,
            relative_module_path,
        )
    )

    if not os.path.isfile(
        original_module_path
    ):
        original_result = execute_function(
            repository_path=original_repository,
            module_path=original_module_path,
            function_name=function_name,
            inputs=inputs,
            python_executable=original_python,
        )

        migrated_result = execute_function(
            repository_path=migrated_repository,
            module_path=migrated_module_path,
            function_name=function_name,
            inputs=inputs,
            python_executable=migrated_python,
        )

        comparison = compare_results(
            original_result,
            migrated_result,
        )

        return {
            "function": function_name,
            "inputs": inputs,
            "original": original_result,
            "migrated": migrated_result,
            "comparison": comparison,
        }

    original_result = execute_function(
        repository_path=original_repository,
        module_path=original_module_path,
        function_name=function_name,
        inputs=inputs,
        python_executable=original_python,
    )

    migrated_result = execute_function(
        repository_path=migrated_repository,
        module_path=migrated_module_path,
        function_name=function_name,
        inputs=inputs,
        python_executable=migrated_python,
    )

    comparison = compare_results(
        original_result,
        migrated_result,
    )

    return {
        "function": function_name,
        "inputs": inputs,
        "original": original_result,
        "migrated": migrated_result,
        "comparison": comparison,
    }


def _get_test_case_value(
    test_case,
    field_name,
):
    """
    Read a field from either a TestCase dataclass
    or a dictionary.
    """

    if isinstance(test_case, dict):
        return test_case.get(
            field_name
        )

    return getattr(
        test_case,
        field_name,
        None,
    )


def run_differential_tests(
    original_repository,
    migrated_repository,
    module_path,
    function_name,
    test_cases,
    original_python=r"C:\Python27\python.exe",
    migrated_python=r"py",
):
    """
    Execute multiple behavioral test cases.
    """

    results = []

    for test_case in test_cases:
        case_function = (
            _get_test_case_value(
                test_case,
                "function",
            )
        )

        inputs = (
            _get_test_case_value(
                test_case,
                "inputs",
            )
        )

        if case_function is None:
            case_function = function_name

        results.append(
            run_differential_test(
                original_repository=(
                    original_repository
                ),
                migrated_repository=(
                    migrated_repository
                ),
                module_path=module_path,
                function_name=case_function,
                inputs=inputs or [],
                original_python=original_python,
                migrated_python=migrated_python,
            )
        )

    return results


def verify_existing_tests(
    original_repository,
    migrated_repository,
    original_python,
    migrated_python,
):
    """
    Verify the repository's existing tests.
    """

    return run_repository_tests(
        original_repository=(
            original_repository
        ),
        migrated_repository=(
            migrated_repository
        ),
        original_python=original_python,
        migrated_python=migrated_python,
    )


def build_migration_scope(
    verification_input,
):
    """
    Build the set of files participating in
    semantic verification.
    """

    return list(
        verification_input.migrated_files
    )


def _get_python_file_functions(
    verification_input,
    file_name,
):
    """
    Get top-level functions belonging to a migrated
    Python file.

    Class methods are excluded because the current
    differential executor executes top-level functions.
    """

    symbols = (
        verification_input.symbols.get(
            file_name,
            [],
        )
    )

    functions = []

    for symbol in symbols:
        if symbol.get("type") != "function":
            continue

        function_name = symbol.get(
            "name"
        )

        if not function_name:
            continue

        if function_name == "__init__":
            continue

        functions.append(
            function_name
        )

    return functions


def _run_generated_behavioral_tests(
    verification_input,
    original_repository,
    migrated_repository,
    original_python,
    migrated_python,
    cases_per_function=3,
):
    """
    Generate behavioral cases for migrated top-level
    functions and execute them differentially.

    Gemini is used by the generator when available.
    The generator falls back automatically when Gemini
    is unavailable or quota-limited.
    """

    all_results = {}

    for file_name in (
        verification_input.migrated_files
    ):
        if not file_name.endswith(".py"):
            continue

        function_names = (
            _get_python_file_functions(
                verification_input,
                file_name,
            )
        )

        if not function_names:
            continue

        migrated_file_path = (
            Path(migrated_repository)
            / file_name
        )

        if not migrated_file_path.exists():
            all_results[file_name] = {
                "status": "SOURCE_NOT_FOUND",
                "functions": {},
            }
            continue

        try:
            generated_cases = (
                generate_llm_cases_for_functions(
                    repository_path=(
                        migrated_repository
                    ),
                    file_name=file_name,
                    function_names=(
                        function_names
                    ),
                    count=cases_per_function,
                )
            )

        except Exception as exc:
            all_results[file_name] = {
                "status": "GENERATION_FAILED",
                "error": str(exc),
                "functions": {},
            }
            continue

        function_results = {}

        for function_name in function_names:
            cases = (
                generated_cases.get(
                    function_name,
                    [],
                )
            )

            if not cases:
                function_results[
                    function_name
                ] = {
                    "status": "NO_TEST_CASES",
                    "cases": [],
                    "results": [],
                }
                continue

            results = run_differential_tests(
                original_repository=(
                    original_repository
                ),
                migrated_repository=(
                    migrated_repository
                ),
                module_path=str(
                    migrated_file_path
                ),
                function_name=function_name,
                test_cases=cases,
                original_python=original_python,
                migrated_python=migrated_python,
            )

            function_results[
                function_name
            ] = {
                "status": "COMPLETED",
                "cases": [
                    case.to_dict()
                    for case in cases
                ],
                "results": results,
            }

        all_results[file_name] = {
            "status": "COMPLETED",
            "functions": function_results,
        }

    return all_results


def _count_behavioral_results(
    behavioral_results,
):
    """
    Count generated behavioral verification results.
    """

    total = 0
    equivalent = 0
    different = 0

    for file_result in (
        behavioral_results.values()
    ):
        functions = file_result.get(
            "functions",
            {},
        )

        for function_result in (
            functions.values()
        ):
            for result in (
                function_result.get(
                    "results",
                    [],
                )
            ):
                total += 1

                if result[
                    "comparison"
                ]["equivalent"]:
                    equivalent += 1
                else:
                    different += 1

    return {
        "total": total,
        "equivalent": equivalent,
        "semantic_differences": different,
    }


def verify_semantics(
    original_repository,
    migrated_repository,
    original_python,
    migrated_python,
    verification_input=None,
):
    """
    Run the complete semantic verification pipeline.

    Existing tests are always executed.

    Generated behavioral tests are executed when
    verification_input is supplied.
    """

    existing_tests = verify_existing_tests(
        original_repository=(
            original_repository
        ),
        migrated_repository=(
            migrated_repository
        ),
        original_python=original_python,
        migrated_python=migrated_python,
    )

    result = {
        "existing_tests": existing_tests,
        "behavioral_tests": {},
        "behavioral_summary": {
            "total": 0,
            "equivalent": 0,
            "semantic_differences": 0,
        },
    }

    if verification_input is None:
        return result

    behavioral_results = (
        _run_generated_behavioral_tests(
            verification_input=(
                verification_input
            ),
            original_repository=(
                original_repository
            ),
            migrated_repository=(
                migrated_repository
            ),
            original_python=original_python,
            migrated_python=migrated_python,
        )
    )

    result[
        "behavioral_tests"
    ] = behavioral_results

    result[
        "behavioral_summary"
    ] = _count_behavioral_results(
        behavioral_results
    )

    return result


def verify_semantics_from_outputs(
    output_directory,
    original_python=r"C:\Python27\python.exe",
    migrated_python=r"py",
):
    """
    Load upstream migration outputs and run
    semantic verification.
    """

    verification_input = (
        load_verification_input(
            output_directory
        )
    )

    return verify_semantics(
        original_repository=(
            verification_input.original_repository
        ),
        migrated_repository=(
            verification_input.migrated_repository
        ),
        original_python=original_python,
        migrated_python=migrated_python,
        verification_input=verification_input,
    )


if __name__ == "__main__":
    print(
        "Semantic verification module loaded."
    )