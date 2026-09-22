def normalize_text(text):
    """
    Normalize command output so harmless formatting differences
    do not appear as semantic differences.
    """
    if text is None:
        return ""

    return text.replace("\r\n", "\n").strip()


def normalize_result(result):
    """
    Convert an ExecutionResult into a stable dictionary
    suitable for comparison.
    """
    return {
        "return_code": result.return_code,
        "stdout": normalize_text(result.stdout),
        "stderr": normalize_text(result.stderr),
        "timed_out": result.timed_out,
    }