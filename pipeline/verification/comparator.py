from .result_normalizer import normalize_result


def _is_function_result(result):
    """
    Detect FunctionExecutionResult objects produced by
    differential_executor.py.
    """

    return (
        hasattr(result, "return_value")
        and hasattr(result, "return_type")
    )


def _values_semantically_equal(original, migrated):
    """
    Compare returned values by observable behavior.

    Python 2 may return an int where Python 3 returns a float
    after a division-related migration.

    Example:
        10 == 10.0

    This should be considered semantically equivalent.

    Other values are compared normally.
    """

    if isinstance(original, bool) or isinstance(
        migrated, bool
    ):
        return original == migrated

    if isinstance(original, (int, float)) and isinstance(
        migrated, (int, float)
    ):
        return original == migrated

    return original == migrated


def _normalize_function_result(result):
    """
    Normalize a function execution result.

    return_type is retained for reporting, but it is NOT
    automatically treated as a semantic difference.
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


def _compare_function_results(original, migrated):
    original_data = _normalize_function_result(
        original
    )

    migrated_data = _normalize_function_result(
        migrated
    )

    differences = {}

    # Status must match.
    if (
        original_data["status"]
        != migrated_data["status"]
    ):
        differences["status"] = {
            "original": original_data["status"],
            "migrated": migrated_data["status"],
        }

    # Return values are compared semantically.
    if not _values_semantically_equal(
        original_data["return_value"],
        migrated_data["return_value"],
    ):
        differences["return_value"] = {
            "original": original_data["return_value"],
            "migrated": migrated_data["return_value"],
        }

    # stdout must match.
    if (
        original_data["stdout"]
        != migrated_data["stdout"]
    ):
        differences["stdout"] = {
            "original": original_data["stdout"],
            "migrated": migrated_data["stdout"],
        }

    # stderr must match.
    if (
        original_data["stderr"]
        != migrated_data["stderr"]
    ):
        differences["stderr"] = {
            "original": original_data["stderr"],
            "migrated": migrated_data["stderr"],
        }

    # Exception behavior must match.
    if (
        original_data["exception_type"]
        != migrated_data["exception_type"]
    ):
        differences["exception_type"] = {
            "original": original_data["exception_type"],
            "migrated": migrated_data["exception_type"],
        }

    if (
        original_data["exception_message"]
        != migrated_data["exception_message"]
    ):
        differences["exception_message"] = {
            "original": original_data["exception_message"],
            "migrated": migrated_data["exception_message"],
        }

    # Timeout behavior must match.
    if (
        original_data["timed_out"]
        != migrated_data["timed_out"]
    ):
        differences["timed_out"] = {
            "original": original_data["timed_out"],
            "migrated": migrated_data["timed_out"],
        }

    # Keep the type difference as metadata rather than treating it
    # as a semantic failure.
    if (
        original_data["return_type"]
        != migrated_data["return_type"]
    ):
        differences.setdefault(
            "return_type",
            {
                "original": original_data["return_type"],
                "migrated": migrated_data["return_type"],
                "semantic_difference": False,
            },
        )

    # Only differences marked as semantic failures should affect
    # equivalence.
    semantic_differences = {
        key: value
        for key, value in differences.items()
        if value.get("semantic_difference", True)
    }

    return {
        "equivalent": len(semantic_differences) == 0,
        "differences": differences,
        "semantic_differences": semantic_differences,
    }


def _compare_dict_results(original, migrated):
    """
    Compare existing repository test execution results.
    """

    original_data = normalize_result(original)
    migrated_data = normalize_result(migrated)

    differences = {}

    keys = set(original_data) | set(migrated_data)

    for key in sorted(keys):
        if original_data.get(key) != migrated_data.get(key):
            differences[key] = {
                "original": original_data.get(key),
                "migrated": migrated_data.get(key),
            }

    return {
        "equivalent": len(differences) == 0,
        "differences": differences,
        "semantic_differences": differences,
    }


def compare_results(original, migrated):
    """
    Compare either:

    1. Existing repository test results, or
    2. Differential function execution results.
    """

    if _is_function_result(original) and _is_function_result(
        migrated
    ):
        return _compare_function_results(
            original,
            migrated,
        )

    return _compare_dict_results(
        original,
        migrated,
    )