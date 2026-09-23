import json
import math
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.verification.semantic_difference_analyzer import (
    analyze_behavioral_result,
)

from pipeline.verification.callable_discovery import (
    discover_callables,
)
from pipeline.verification.differential_executor import (
    execute_function,
)
from pipeline.verification.test_generator import (
    generate_cases_for_callables,
)
from pipeline.verification.verification_input import (
    load_verification_input,
)


def _values_semantically_equal(
    left,
    right,
):
    """
    Compare two values semantically.

    The comparison is recursive and does not require exact
    Python runtime types when the values are behaviorally
    equivalent.
    """

    if left is None or right is None:
        return left is None and right is None

    if isinstance(
        left,
        bool,
    ) or isinstance(
        right,
        bool,
    ):
        return (
            isinstance(left, bool)
            and isinstance(right, bool)
            and left == right
        )

    if isinstance(
        left,
        (int, float),
    ) and isinstance(
        right,
        (int, float),
    ):

        try:

            if (
                isinstance(left, float)
                and math.isnan(left)
            ):
                return (
                    isinstance(right, float)
                    and math.isnan(right)
                )

            if (
                isinstance(right, float)
                and math.isnan(right)
            ):
                return False

            return left == right

        except Exception:
            return False

    if isinstance(
        left,
        list,
    ) and isinstance(
        right,
        list,
    ):

        if len(left) != len(right):
            return False

        return all(
            _values_semantically_equal(
                left_item,
                right_item,
            )
            for left_item, right_item in zip(
                left,
                right,
            )
        )

    if isinstance(
        left,
        tuple,
    ) and isinstance(
        right,
        tuple,
    ):

        if len(left) != len(right):
            return False

        return all(
            _values_semantically_equal(
                left_item,
                right_item,
            )
            for left_item, right_item in zip(
                left,
                right,
            )
        )

    if isinstance(
        left,
        dict,
    ) and isinstance(
        right,
        dict,
    ):

        if set(left.keys()) != set(
            right.keys()
        ):
            return False

        return all(
            _values_semantically_equal(
                left[key],
                right[key],
            )
            for key in left
        )

    if isinstance(
        left,
        set,
    ) and isinstance(
        right,
        set,
    ):

        return left == right

    return left == right


def _compare_execution_results(
    original,
    migrated,
):
    """
    Compare two callable execution results.

    Return types are deliberately not treated as a semantic
    difference when the returned values are equivalent.
    """

    differences = []

    if original.status != migrated.status:

        differences.append(
            {
                "field": "status",
                "original": original.status,
                "migrated": migrated.status,
            }
        )

    if not _values_semantically_equal(
        original.return_value,
        migrated.return_value,
    ):

        differences.append(
            {
                "field": "return_value",
                "original": original.return_value,
                "migrated": migrated.return_value,
            }
        )

    if original.stdout != migrated.stdout:

        differences.append(
            {
                "field": "stdout",
                "original": original.stdout,
                "migrated": migrated.stdout,
            }
        )

    if original.stderr != migrated.stderr:

        differences.append(
            {
                "field": "stderr",
                "original": original.stderr,
                "migrated": migrated.stderr,
            }
        )

    if (
        original.exception_type
        != migrated.exception_type
    ):

        differences.append(
            {
                "field": "exception_type",
                "original": original.exception_type,
                "migrated": migrated.exception_type,
            }
        )

    if (
        original.exception_message
        != migrated.exception_message
    ):

        differences.append(
            {
                "field": "exception_message",
                "original": original.exception_message,
                "migrated": migrated.exception_message,
            }
        )

    if (
        original.timed_out
        != migrated.timed_out
    ):

        differences.append(
            {
                "field": "timed_out",
                "original": original.timed_out,
                "migrated": migrated.timed_out,
            }
        )

    return {
        "equivalent": not differences,
        "semantic_difference": bool(
            differences
        ),
        "differences": differences,
    }


def _serialize_execution_result(
    result,
):
    """
    Convert an execution result into a JSON-friendly
    dictionary.
    """

    return {
        "status": result.status,
        "return_value": result.return_value,
        "return_type": result.return_type,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exception_type": result.exception_type,
        "exception_message": result.exception_message,
        "timed_out": result.timed_out,
    }


def _normalize_python_command(
    python_executable
):
    """
    Convert a configured Python command into the argument
    list expected by subprocess.run().

    Examples:

        "py -2"
            ->
        ["py", "-2"]

        "py -3"
            ->
        ["py", "-3"]

        "python"
            ->
        ["python"]
    """

    if isinstance(
        python_executable,
        (list, tuple),
    ):
        return [
            str(part)
            for part in python_executable
        ]

    if not python_executable:
        return [
            "python"
        ]

    return shlex.split(
        str(
            python_executable
        ),
        posix=False,
    )


def _repository_test_command(
    python_executable,
):
    """
    Build a repository-independent unittest command.

    The Python executable may be supplied as:

        "py -2"

    or:

        "py -3"

    and is normalized into separate subprocess arguments.
    """

    python_command = (
        _normalize_python_command(
            python_executable
        )
    )

    return (
        python_command
        + [
            "-m",
            "unittest",
            "discover",
            "-v",
            "-s",
            "tests",
            "-p",
            "test*.py",
        ]
    )


def _run_test_suite(
    repository_path,
    python_executable,
    timeout=120,
):
    """
    Execute the repository's existing unittest suite.
    """

    repository_path = Path(
        repository_path
    ).resolve()

    tests_directory = (
        repository_path
        / "tests"
    )

    if not tests_directory.exists():
        return {
            "status": "NO_TESTS_DIRECTORY",
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "test_count": 0,
        }

    command = _repository_test_command(
        python_executable
    )

    try:

        completed = subprocess.run(
            command,
            cwd=str(repository_path),
            capture_output=True,
            text=True,
            timeout=timeout,
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

        if isinstance(
            stdout,
            bytes,
        ):
            stdout = stdout.decode(
                errors="replace"
            )

        if isinstance(
            stderr,
            bytes,
        ):
            stderr = stderr.decode(
                errors="replace"
            )

        return {
            "status": "TIMEOUT",
            "return_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "test_count": 0,
        }

    except FileNotFoundError as exc:

        return {
            "status": "EXECUTION_FAILED",
            "return_code": None,
            "stdout": "",
            "stderr": str(exc),
            "test_count": 0,
        }

    output = (
        completed.stdout
        + "\n"
        + completed.stderr
    )

    test_count = 0

    for line in output.splitlines():

        stripped = line.strip()

        if (
            stripped.startswith(
                "Ran "
            )
            and " tests" in stripped
        ):

            try:

                test_count = int(
                    stripped.split(
                        "Ran ",
                        1,
                    )[1].split(
                        " tests",
                        1,
                    )[0]
                )

            except Exception:
                pass

    if (
        completed.returncode == 0
        and test_count > 0
    ):
        status = "PASS"

    elif (
        completed.returncode == 0
        and test_count == 0
    ):
        status = "NO_TESTS_RUN"

    else:
        status = "FAIL"

    return {
        "status": status,
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "test_count": test_count,
    }


def _copy_existing_tests_to_migrated_repository(
    original_repository,
    migrated_repository,
):
    """
    Create a temporary migrated verification workspace.

    Existing tests are copied from the original repository
    into the migrated repository so the same tests execute
    against both implementations.

    The real migrated repository is never modified.
    """

    temporary_directory = tempfile.mkdtemp(
        prefix="semantic_verification_"
    )

    temporary_repository = (
        Path(temporary_directory)
        / "migrated"
    )

    shutil.copytree(
        migrated_repository,
        temporary_repository,
    )

    original_tests = (
        Path(original_repository)
        / "tests"
    )

    migrated_tests = (
        temporary_repository
        / "tests"
    )

    if original_tests.exists():

        if migrated_tests.exists():
            shutil.rmtree(
                migrated_tests
            )

        shutil.copytree(
            original_tests,
            migrated_tests,
        )

    return (
        temporary_repository,
        temporary_directory,
    )


def _run_existing_tests_differentially(
    original_repository,
    migrated_repository,
    python2_executable,
    python3_executable,
):
    """
    Run the existing repository tests against both versions.

    The exact same test files are used for both executions.

    This prevents an empty migrated tests directory from
    being incorrectly interpreted as a successful test run.
    """

    original_result = _run_test_suite(
        repository_path=original_repository,
        python_executable=python2_executable,
    )

    temporary_repository = None
    temporary_directory = None

    try:

        (
            temporary_repository,
            temporary_directory,
        ) = _copy_existing_tests_to_migrated_repository(
            original_repository=original_repository,
            migrated_repository=migrated_repository,
        )

        migrated_result = _run_test_suite(
            repository_path=temporary_repository,
            python_executable=python3_executable,
        )

    finally:

        if temporary_directory is not None:

            shutil.rmtree(
                temporary_directory,
                ignore_errors=True,
            )

    equivalent = (
        original_result["status"] == "PASS"
        and migrated_result["status"] == "PASS"
    )

    return {
        "equivalent": equivalent,
        "original": original_result,
        "migrated": migrated_result,
        "detailed": [
            {
                "test_suite": "existing_tests",
                "equivalent": equivalent,
                "original": original_result,
                "migrated": migrated_result,
            }
        ],
    }


def _callable_metadata(
    callable_info,
):
    """
    Convert CallableInfo into a serializable dictionary.
    """

    if hasattr(
        callable_info,
        "to_dict",
    ):
        return callable_info.to_dict()

    return {
        "file": getattr(
            callable_info,
            "file_name",
            None,
        ),
        "qualified_name": getattr(
            callable_info,
            "qualified_name",
            None,
        ),
        "function_name": getattr(
            callable_info,
            "function_name",
            None,
        ),
        "kind": getattr(
            callable_info,
            "kind",
            "function",
        ),
        "class_name": getattr(
            callable_info,
            "class_name",
            None,
        ),
        "line": getattr(
            callable_info,
            "line",
            0,
        ),
        "parameters": getattr(
            callable_info,
            "parameters",
            [],
        ),
    }


def run_differential_test(
    original_repository,
    migrated_repository,
    callable_info,
    inputs=None,
    constructor_inputs=None,
    python2_executable="py -2",
    python3_executable="py -3",
    timeout=30,
):
    """
    Execute one callable in both repositories and compare
    the observed behavior.

    This is the semantic source of truth.

    No LLM output is trusted as a correctness result.
    """

    if inputs is None:
        inputs = []

    file_name = callable_info.file_name
    function_name = callable_info.function_name
    callable_kind = callable_info.kind
    class_name = callable_info.class_name

    original_module = (
        Path(original_repository)
        / file_name
    )

    migrated_module = (
        Path(migrated_repository)
        / file_name
    )

    original_result = execute_function(
        repository_path=str(
            original_repository
        ),
        module_path=str(
            original_module
        ),
        function_name=function_name,
        inputs=inputs,
        python_executable=python2_executable,
        timeout=timeout,
        class_name=class_name,
        callable_kind=callable_kind,
        constructor_inputs=constructor_inputs,
    )

    migrated_result = execute_function(
        repository_path=str(
            migrated_repository
        ),
        module_path=str(
            migrated_module
        ),
        function_name=function_name,
        inputs=inputs,
        python_executable=python3_executable,
        timeout=timeout,
        class_name=class_name,
        callable_kind=callable_kind,
        constructor_inputs=constructor_inputs,
    )

    comparison = _compare_execution_results(
        original=original_result,
        migrated=migrated_result,
    )

    result = {
        "callable": _callable_metadata(
            callable_info
        ),
        "inputs": inputs,
        "constructor_inputs": constructor_inputs,
        "original": _serialize_execution_result(
            original_result
        ),
        "migrated": _serialize_execution_result(
            migrated_result
        ),
        "comparison": comparison,
    }

    # The comparison above remains the source of truth.
    # The analyzer only explains detected differences.
    return analyze_behavioral_result(
        result
    )


def _discover_verification_callables(
    verification_input,
):
    """
    Discover callable structure from migrated Python source.

    This intentionally does not use the upstream symbol list
    for invocation because the upstream graph does not encode
    class ownership for methods.
    """

    return discover_callables(
        repository_path=verification_input.migrated_repository,
        file_names=verification_input.migrated_files,
    )


def _run_generated_behavioral_tests(
    verification_input,
    python2_executable="py -2",
    python3_executable="py -3",
    cases_per_callable=3,
):
    """
    Generate and execute behavioral scenarios for every
    discovered callable.

    Existing repository tests are separate and are always
    executed independently.
    """

    callables = (
        _discover_verification_callables(
            verification_input
        )
    )

    generated_cases = (
        generate_cases_for_callables(
            callables=callables,
            count=cases_per_callable,
            repository_path=verification_input.migrated_repository,
        )
    )

    detailed_results = []

    for callable_info in callables:

        qualified_name = (
            callable_info.qualified_name
        )

        cases = generated_cases.get(
            qualified_name,
            [],
        )

        for index, case in enumerate(
            cases,
            start=1,
        ):

            case_inputs = case.inputs

            constructor_inputs = (
                case.constructor_inputs
            )

            result = run_differential_test(
                original_repository=(
                    verification_input.original_repository
                ),
                migrated_repository=(
                    verification_input.migrated_repository
                ),
                callable_info=callable_info,
                inputs=case_inputs,
                constructor_inputs=constructor_inputs,
                python2_executable=python2_executable,
                python3_executable=python3_executable,
            )

            result[
                "case_number"
            ] = index

            result[
                "generation_metadata"
            ] = case.metadata

            detailed_results.append(
                result
            )

    equivalent_count = sum(
        1
        for result in detailed_results
        if result["comparison"][
            "equivalent"
        ]
    )

    difference_count = sum(
        1
        for result in detailed_results
        if result["comparison"][
            "semantic_difference"
        ]
    )

    return {
        "callable_count": len(
            callables
        ),
        "case_count": len(
            detailed_results
        ),
        "equivalent": equivalent_count,
        "semantic_differences": difference_count,
        "detailed": detailed_results,
    }


def _load_python_executables():
    """
    Read optional interpreter configuration.

    Defaults match the local Python 2 -> Python 3 migration
    environment.
    """

    python2 = os.environ.get(
        "PYTHON2_EXECUTABLE",
        "py -2",
    )

    python3 = os.environ.get(
        "PYTHON3_EXECUTABLE",
        "py -3",
    )

    return (
        python2,
        python3,
    )


def verify_semantics(
    verification_input,
    python2_executable=None,
    python3_executable=None,
    cases_per_callable=3,
):
    """
    Run the complete semantic verification stage.

    Verification always includes:

    1. Existing repository tests.
    2. Generated behavioral tests.

    Generated behavioral tests are differential:
    the original Python 2 implementation and migrated
    Python 3 implementation are both executed.

    The LLM only proposes candidate scenarios.
    """

    (
        default_python2,
        default_python3,
    ) = _load_python_executables()

    if python2_executable is None:
        python2_executable = default_python2

    if python3_executable is None:
        python3_executable = default_python3

    existing_tests = (
        _run_existing_tests_differentially(
            original_repository=(
                verification_input.original_repository
            ),
            migrated_repository=(
                verification_input.migrated_repository
            ),
            python2_executable=python2_executable,
            python3_executable=python3_executable,
        )
    )

    behavioral_tests = (
        _run_generated_behavioral_tests(
            verification_input=verification_input,
            python2_executable=python2_executable,
            python3_executable=python3_executable,
            cases_per_callable=cases_per_callable,
        )
    )

    return {
        "status": (
            "PASS"
            if (
                existing_tests["equivalent"]
                and behavioral_tests[
                    "semantic_differences"
                ] == 0
            )
            else "FAIL"
        ),
        "existing_tests": existing_tests,
        "behavioral_tests": behavioral_tests,
        "summary": {
            "existing_tests_equivalent": (
                existing_tests["equivalent"]
            ),
            "behavioral_cases": behavioral_tests[
                "case_count"
            ],
            "behavioral_equivalent": behavioral_tests[
                "equivalent"
            ],
            "behavioral_semantic_differences": (
                behavioral_tests[
                    "semantic_differences"
                ]
            ),
        },
    }


def verify_semantics_from_outputs(
    output_directory,
    python2_executable=None,
    python3_executable=None,
    cases_per_callable=3,
):
    """
    Load upstream migration outputs and execute semantic
    verification.
    """

    verification_input = (
        load_verification_input(
            output_directory
        )
    )

    return verify_semantics(
        verification_input=verification_input,
        python2_executable=python2_executable,
        python3_executable=python3_executable,
        cases_per_callable=cases_per_callable,
    )


def save_verification_report(
    report,
    output_path,
):
    """
    Save the verification report as JSON.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            report,
            handle,
            indent=2,
            ensure_ascii=False,
        )


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Run semantic verification for a "
            "Python 2 -> Python 3 migration."
        )
    )

    parser.add_argument(
        "output_directory",
        help=(
            "Directory containing the upstream "
            "migration-analysis outputs."
        ),
    )

    parser.add_argument(
        "--cases-per-callable",
        type=int,
        default=3,
        help=(
            "Number of generated behavioral cases "
            "per callable."
        ),
    )

    parser.add_argument(
        "--python2",
        default=None,
        help=(
            "Python 2 executable. Defaults to "
            "PYTHON2_EXECUTABLE or py -2."
        ),
    )

    parser.add_argument(
        "--python3",
        default=None,
        help=(
            "Python 3 executable. Defaults to "
            "PYTHON3_EXECUTABLE or py -3."
        ),
    )

    parser.add_argument(
        "--report",
        default=None,
        help=(
            "Optional JSON output path."
        ),
    )

    args = parser.parse_args()

    report = verify_semantics_from_outputs(
        output_directory=args.output_directory,
        python2_executable=args.python2,
        python3_executable=args.python3,
        cases_per_callable=(
            args.cases_per_callable
        ),
    )

    if args.report:

        save_verification_report(
            report=report,
            output_path=args.report,
        )

    print(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        )
    )