"""
Generic semantic difference analysis.

This module does not decide whether two executions are equivalent.
That decision remains in semantic_verifier.py.

This module only explains an already-detected difference in a
human-readable, structured form.
"""


def _type_name(value):
    if value is None:
        return "NoneType"

    if isinstance(value, dict) and "__type__" in value:
        return value["__type__"]

    return type(value).__name__


def _format_value(value):
    return repr(value)


def _numeric_difference_analysis(original, migrated):
    return {
        "category": "numeric_value_change",
        "message": "Return value changed numerically.",
        "original_value": original,
        "migrated_value": migrated,
        "original_type": _type_name(original),
        "migrated_type": _type_name(migrated),
        "delta": migrated - original,
    }


def _string_difference_analysis(original, migrated):
    return {
        "category": "string_value_change",
        "message": "Return value changed from one string to another.",
        "original_value": original,
        "migrated_value": migrated,
        "original_type": _type_name(original),
        "migrated_type": _type_name(migrated),
    }


def _collection_difference_analysis(original, migrated):
    return {
        "category": "collection_value_change",
        "message": "Returned collection differs between Python 2 and Python 3.",
        "original_value": original,
        "migrated_value": migrated,
        "original_type": _type_name(original),
        "migrated_type": _type_name(migrated),
    }


def _object_difference_analysis(original, migrated):
    original_type = _type_name(original)
    migrated_type = _type_name(migrated)

    return {
        "category": "object_state_change",
        "message": "Returned object state differs between Python 2 and Python 3.",
        "original_type": original_type,
        "migrated_type": migrated_type,
        "original_state": original,
        "migrated_state": migrated,
    }


def _analyze_return_value_difference(original, migrated):
    # Check serialized user-defined objects BEFORE generic dictionaries.
    if (
        isinstance(original, dict)
        and "__type__" in original
        and "attributes" in original
        and isinstance(migrated, dict)
        and "__type__" in migrated
        and "attributes" in migrated
    ):
        return _object_difference_analysis(original, migrated)

    if isinstance(original, (int, float)) and not isinstance(original, bool):
        if isinstance(migrated, (int, float)) and not isinstance(migrated, bool):
            return _numeric_difference_analysis(original, migrated)

    if isinstance(original, str) and isinstance(migrated, str):
        return _string_difference_analysis(original, migrated)

    if isinstance(original, (list, tuple, dict, set)) or isinstance(
        migrated, (list, tuple, dict, set)
    ):
        return _collection_difference_analysis(original, migrated)

    return {
        "category": "value_change",
        "message": "Return value changed.",
        "original_value": original,
        "migrated_value": migrated,
        "original_type": _type_name(original),
        "migrated_type": _type_name(migrated),
    }


def _analyze_status_difference(original, migrated):
    return {
        "category": "execution_status_change",
        "message": "Execution status changed between Python 2 and Python 3.",
        "original_status": original.get("status"),
        "migrated_status": migrated.get("status"),
    }


def _analyze_exception_type_difference(original, migrated):
    return {
        "category": "exception_type_change",
        "message": "The exception type changed between Python 2 and Python 3.",
        "original_exception_type": original.get("exception_type"),
        "migrated_exception_type": migrated.get("exception_type"),
    }


def _analyze_exception_message_difference(original, migrated):
    return {
        "category": "exception_message_change",
        "message": "The exception message changed between Python 2 and Python 3.",
        "original_exception_message": original.get("exception_message"),
        "migrated_exception_message": migrated.get("exception_message"),
    }


def _analyze_output_difference(original, migrated):
    return {
        "category": "stdout_change",
        "message": "Standard output changed between Python 2 and Python 3.",
        "original_stdout": original.get("stdout", ""),
        "migrated_stdout": migrated.get("stdout", ""),
    }


def analyze_difference(difference, original, migrated):
    field = difference.get("field")

    if field == "return_value":
        return _analyze_return_value_difference(
            original.get("return_value"),
            migrated.get("return_value"),
        )

    if field == "status":
        return _analyze_status_difference(original, migrated)

    if field == "exception_type":
        return _analyze_exception_type_difference(original, migrated)

    if field == "exception_message":
        return _analyze_exception_message_difference(original, migrated)

    if field == "stdout":
        return _analyze_output_difference(original, migrated)

    return {
        "category": "execution_difference",
        "message": "Execution result differs between Python 2 and Python 3.",
        "field": field,
        "original_value": difference.get("original"),
        "migrated_value": difference.get("migrated"),
    }


def analyze_comparison(comparison, original, migrated):
    differences = comparison.get("differences", [])

    if not differences:
        return None

    analyses = []

    for difference in differences:
        analyses.append(
            analyze_difference(
                difference,
                original,
                migrated,
            )
        )

    return {
        "difference_count": len(analyses),
        "details": analyses,
    }


def analyze_behavioral_result(result):
    comparison = result.get("comparison")

    if not comparison:
        return result

    if not comparison.get("semantic_difference"):
        return result

    original = result.get("original", {})
    migrated = result.get("migrated", {})

    analysis = analyze_comparison(
        comparison,
        original,
        migrated,
    )

    result["analysis"] = analysis

    return result