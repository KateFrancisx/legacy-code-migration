from .result_normalizer import normalize_result


def compare_results(original, migrated):
    """
    Compare execution results from the original and migrated
    repositories.
    """

    original = normalize_result(original)
    migrated = normalize_result(migrated)

    differences = {}

    for key in original:
        if original[key] != migrated[key]:
            differences[key] = {
                "original": original[key],
                "migrated": migrated[key],
            }

    return {
        "equivalent": len(differences) == 0,
        "differences": differences,
    }