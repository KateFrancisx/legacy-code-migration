import json
from pathlib import Path

from sklearn.ensemble import IsolationForest


def _safe_number(value):
    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)):
        return value

    return 0


def _behavioral_case_count(semantic_result):
    """
    Read the behavioral case count from the actual semantic
    verification report structure.
    """

    behavioral = semantic_result.get(
        "behavioral_tests",
        {},
    )

    return int(
        _safe_number(
            behavioral.get(
                "case_count",
                0,
            )
        )
    )


def _semantic_difference_count(semantic_result):
    """
    Read the total number of semantic differences from the
    actual semantic verification report structure.

    This represents executed cases with differences, not
    necessarily unique underlying differences.
    """

    behavioral = semantic_result.get(
        "behavioral_tests",
        {},
    )

    return int(
        _safe_number(
            behavioral.get(
                "semantic_differences",
                0,
            )
        )
    )


def _existing_test_failed(semantic_result):
    """
    Existing tests are considered failed when the existing
    test differential verification is not equivalent.
    """

    existing = semantic_result.get(
        "existing_tests",
        {},
    )

    if not existing:
        return 0

    if existing.get(
        "equivalent"
    ) is False:
        return 1

    return 0


def _canonicalize_for_key(value):
    """
    Convert a JSON-compatible value into a stable representation
    that can be used to identify duplicate behavioral differences.

    This does not modify the actual result data. It is only used
    internally for deduplication.
    """

    try:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        return repr(value)


def _difference_case_key(result):
    """
    Build a stable identity for one semantic difference.

    The key includes:

      - file
      - qualified callable name
      - callable kind
      - class name
      - inputs
      - constructor inputs
      - actual comparison differences
      - semantic analysis details

    Case number is intentionally excluded.

    Therefore, if the same behavioral scenario is executed
    multiple times and produces the same semantic difference,
    it is represented once in the risk report.
    """

    callable_info = result.get(
        "callable",
        {},
    )

    comparison = result.get(
        "comparison",
        {},
    )

    analysis = result.get(
        "analysis",
        {},
    )

    return (
        _canonicalize_for_key(
            {
                "file": callable_info.get(
                    "file"
                ),
                "qualified_name": callable_info.get(
                    "qualified_name"
                ),
                "function_name": callable_info.get(
                    "function_name"
                ),
                "kind": callable_info.get(
                    "kind"
                ),
                "class_name": callable_info.get(
                    "class_name"
                ),
                "inputs": result.get(
                    "inputs"
                ),
                "constructor_inputs": result.get(
                    "constructor_inputs"
                ),
                "differences": comparison.get(
                    "differences",
                    [],
                ),
                "analysis": analysis.get(
                    "details",
                    [],
                ),
            }
        )
    )


def _deduplicate_difference_cases(
    difference_cases,
):
    """
    Remove duplicate semantic difference cases while preserving
    the order in which the first occurrence appeared.

    Multiple executions of the exact same behavioral difference
    are treated as one underlying issue for reporting.
    """

    unique_cases = []
    seen = set()

    for result in difference_cases:

        key = _difference_case_key(
            result
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique_cases.append(
            result
        )

    return unique_cases


def _file_behavioral_statistics(
    file_name,
    semantic_result,
):
    """
    Extract behavioral verification information for one file.

    The semantic verifier already executed the cases. This
    function only reads that existing JSON result.

    No new test cases are generated here.

    semantic_differences counts all executions that differ.

    unique_semantic_differences counts distinct underlying
    differences after deduplication.

    difference_cases contains only the unique differences.
    """

    behavioral = semantic_result.get(
        "behavioral_tests",
        {},
    )

    detailed = behavioral.get(
        "detailed",
        [],
    )

    file_cases = []
    file_differences = []

    for result in detailed:

        callable_info = result.get(
            "callable",
            {},
        )

        result_file = callable_info.get(
            "file"
        )

        if result_file != file_name:
            continue

        file_cases.append(
            result
        )

        comparison = result.get(
            "comparison",
            {},
        )

        if comparison.get(
            "semantic_difference"
        ) is True:

            file_differences.append(
                result
            )

    unique_file_differences = (
        _deduplicate_difference_cases(
            file_differences
        )
    )

    return {
        "behavioral_cases": len(
            file_cases
        ),
        "semantic_differences": len(
            file_differences
        ),
        "unique_semantic_differences": len(
            unique_file_differences
        ),
        "difference_cases": (
            unique_file_differences
        ),
    }


def _file_features(
    file_name,
    verification_input,
    semantic_result,
):
    """
    Build generic risk features for one migrated file.

    All behavioral information comes from the already-created
    semantic verification report.
    """

    symbols = verification_input.symbols.get(
        file_name,
        [],
    )

    function_count = sum(
        1
        for symbol in symbols
        if symbol.get("type") == "function"
    )

    class_count = sum(
        1
        for symbol in symbols
        if symbol.get("type") == "class"
    )

    dependencies = verification_input.dependencies

    dependent_count = 0

    for source_file, targets in dependencies.items():

        if source_file == file_name:
            continue

        if isinstance(
            targets,
            list,
        ):

            for target in targets:

                if (
                    isinstance(target, str)
                    and target == file_name
                ):
                    dependent_count += 1

                elif (
                    isinstance(target, dict)
                    and target.get("file")
                    == file_name
                ):
                    dependent_count += 1

    behavioral_statistics = (
        _file_behavioral_statistics(
            file_name=file_name,
            semantic_result=semantic_result,
        )
    )

    behavioral_cases = behavioral_statistics[
        "behavioral_cases"
    ]

    semantic_differences = (
        behavioral_statistics[
            "semantic_differences"
        ]
    )

    semantic_difference_rate = 0.0

    if behavioral_cases > 0:

        semantic_difference_rate = (
            semantic_differences
            / behavioral_cases
        )

    existing_test_failed = (
        _existing_test_failed(
            semantic_result
        )
    )

    return {
        "function_count": function_count,
        "class_count": class_count,
        "dependent_count": dependent_count,
        "behavioral_cases": behavioral_cases,
        "semantic_differences": semantic_differences,
        "unique_semantic_differences": (
            behavioral_statistics[
                "unique_semantic_differences"
            ]
        ),
        "semantic_difference_rate": (
            semantic_difference_rate
        ),
        "existing_test_failed": (
            existing_test_failed
        ),
        "difference_cases": (
            behavioral_statistics[
                "difference_cases"
            ]
        ),
    }


def _risk_label(
    anomaly_score,
    semantic_difference_rate,
    semantic_differences,
    existing_test_failed,
):
    """
    Convert measured verification evidence into a risk label.

    Semantic differences and existing test failures are
    concrete verification evidence.

    IsolationForest is used as an additional anomaly signal.
    """

    if existing_test_failed:
        return "HIGH"

    if semantic_difference_rate >= 0.50:
        return "HIGH"

    if semantic_differences > 0:

        if anomaly_score < -0.10:
            return "HIGH"

        return "MEDIUM"

    if anomaly_score < 0:
        return "MEDIUM"

    return "LOW"


def _build_matrix(feature_rows):
    """
    Build the numerical feature matrix used by IsolationForest.
    """

    matrix = []

    for _, features in feature_rows:

        matrix.append(
            [
                features["function_count"],
                features["class_count"],
                features["dependent_count"],
                features["behavioral_cases"],
                features["semantic_differences"],
                features["semantic_difference_rate"],
                features["existing_test_failed"],
            ]
        )

    return matrix


def analyze_migration_risk(
    verification_input,
    semantic_result,
):
    """
    Analyze migration risk using the existing semantic
    verification result.

    IMPORTANT:

    This function does NOT:
      - call the LLM
      - generate new behavioral tests
      - execute Python 2
      - execute Python 3

    It only analyzes the verification JSON that already exists.

    Duplicate semantic differences are deduplicated in the
    per-file difference_cases output.
    """

    migrated_files = (
        verification_input.migrated_files
    )

    if not migrated_files:

        return {
            "status": "NO_MIGRATED_FILES",
            "model": "IsolationForest",
            "files": {},
        }

    feature_rows = []

    for file_name in migrated_files:

        features = _file_features(
            file_name=file_name,
            verification_input=verification_input,
            semantic_result=semantic_result,
        )

        feature_rows.append(
            (
                file_name,
                features,
            )
        )

    matrix = _build_matrix(
        feature_rows
    )

    # IsolationForest is useful as an additional signal,
    # but semantic verification remains the primary evidence.
    #
    # For a single migrated file there is not enough data
    # for meaningful anomaly detection, so use a neutral
    # anomaly score instead of pretending the model learned
    # something from one row.
    if len(matrix) >= 2:

        model = IsolationForest(
            n_estimators=100,
            contamination="auto",
            random_state=42,
        )

        model.fit(matrix)

        scores = model.decision_function(
            matrix
        )

        predictions = model.predict(
            matrix
        )

    else:

        scores = [0.0] * len(matrix)
        predictions = [1] * len(matrix)

    results = {}

    for index, (
        file_name,
        features,
    ) in enumerate(
        feature_rows
    ):

        anomaly_score = float(
            scores[index]
        )

        prediction = int(
            predictions[index]
        )

        risk = _risk_label(
            anomaly_score=anomaly_score,
            semantic_difference_rate=(
                features[
                    "semantic_difference_rate"
                ]
            ),
            semantic_differences=(
                features[
                    "semantic_differences"
                ]
            ),
            existing_test_failed=(
                features[
                    "existing_test_failed"
                ]
            ),
        )

        reasons = []

        if features[
            "semantic_differences"
        ] > 0:

            reasons.append(
                "Semantic differences detected"
            )

        if features[
            "existing_test_failed"
        ]:

            reasons.append(
                "Existing tests failed"
            )

        if features[
            "dependent_count"
        ] > 0:

            reasons.append(
                "File has dependent modules"
            )

        if features[
            "semantic_difference_rate"
        ] >= 0.50:

            reasons.append(
                "High semantic difference rate"
            )

        if not reasons:

            reasons.append(
                "No major verification issues detected"
            )

        results[file_name] = {
            "risk": risk,
            "anomaly_score": anomaly_score,
            "anomaly_prediction": prediction,
            "features": features,
            "reasons": reasons,
        }

    return {
        "status": "SUCCESS",
        "model": "IsolationForest",
        "source": "semantic_verification_report",
        "feature_names": [
            "function_count",
            "class_count",
            "dependent_count",
            "behavioral_cases",
            "semantic_differences",
            "unique_semantic_differences",
            "semantic_difference_rate",
            "existing_test_failed",
        ],
        "files": results,
    }


def save_risk_report(
    result,
    output_path,
):
    """
    Save the risk analysis result as JSON.
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
            result,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return str(
        output_path
    )


if __name__ == "__main__":

    import argparse

    from pipeline.verification.verification_input import (
        load_verification_input,
    )

    parser = argparse.ArgumentParser(
        description=(
            "Analyze migration risk from an existing "
            "semantic verification report."
        )
    )

    parser.add_argument(
        "output_directory",
        help=(
            "Directory containing the migration "
            "metadata outputs."
        ),
    )

    parser.add_argument(
        "--semantic-report",
        required=True,
        help=(
            "Existing semantic verification JSON report."
        ),
    )

    parser.add_argument(
        "--report",
        default=None,
        help=(
            "Optional path for the generated risk report."
        ),
    )

    args = parser.parse_args()

    verification_input = (
        load_verification_input(
            args.output_directory
        )
    )

    with open(
        args.semantic_report,
        "r",
        encoding="utf-8",
    ) as handle:

        semantic_result = json.load(
            handle
        )

    result = analyze_migration_risk(
        verification_input=verification_input,
        semantic_result=semantic_result,
    )

    if args.report:

        save_risk_report(
            result=result,
            output_path=args.report,
        )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )