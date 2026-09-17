from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from pipeline.dependency import (
    DependencyAnalyzer,
    RepositoryContextBuilder,
)


def print_dependency_graph(
    result,
):
    print("\n" + "=" * 70)
    print("DEPENDENCY CHAIN")
    print("=" * 70)

    graph = result.get(
        "graph",
        {},
    )

    if not graph:
        print("No dependency edges found.")
        return

    for source, edges in graph.items():

        for edge in edges:

            details = edge.get(
                "details",
                {},
            )

            detail_text = ""

            if details:
                detail_text = (
                    f" | {details}"
                )

            print(
                f"{source}"
                f" --[{edge['type']}]--> "
                f"{edge['target']}"
                f"{detail_text}"
            )


def main():

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "  python scripts/test_dependency_analysis.py "
            "<repo_path> [file.py] [function]"
        )

        sys.exit(1)

    repo_path = sys.argv[1]

    print("=" * 70)
    print("DEPENDENCY ANALYSIS")
    print("=" * 70)

    analyzer = DependencyAnalyzer(
        repo_path
    )

    result = analyzer.analyze()

    statistics = result[
        "statistics"
    ]

    print(
        f"Repository: "
        f"{result['repository']}"
    )

    print(
        f"Python files: "
        f"{result['file_count']}"
    )

    print(
        f"Dependency edges: "
        f"{statistics['dependency_edges']}"
    )

    print(
        f"Import edges: "
        f"{statistics['import_edges']}"
    )

    print(
        f"From-import edges: "
        f"{statistics['from_import_edges']}"
    )

    print(
        f"Function-call edges: "
        f"{statistics['function_call_edges']}"
    )

    print(
        f"Inheritance edges: "
        f"{statistics['inheritance_edges']}"
    )

    # --------------------------------------------------------------
    # Save dependency graph
    # --------------------------------------------------------------

    repo_name = Path(
        repo_path
    ).resolve().name

    graph_output = (
        PROJECT_ROOT
        / "outputs"
        / f"{repo_name}_dependency_graph.json"
    )

    analyzer.save(
        str(graph_output)
    )

    print(
        f"\nDependency graph saved to:\n"
        f"{graph_output}"
    )

    # --------------------------------------------------------------
    # Print graph
    # --------------------------------------------------------------

    print_dependency_graph(
        result
    )

    # --------------------------------------------------------------
    # No target supplied
    # --------------------------------------------------------------

    if len(sys.argv) < 3:

        print(
            "\nNo target file supplied."
        )

        return

    # --------------------------------------------------------------
    # Build repository context
    # --------------------------------------------------------------

    target_file = sys.argv[2]

    builder = RepositoryContextBuilder(
        repo_path=repo_path,
        dependency_graph=result,
    )

    if len(sys.argv) >= 4:

        function_name = sys.argv[3]

        context = (
            builder.build_for_function(
                target_file,
                function_name,
            )
        )

    else:

        context = (
            builder.build_for_file(
                target_file
            )
        )

    # --------------------------------------------------------------
    # Save context
    # --------------------------------------------------------------

    context_output = (
        PROJECT_ROOT
        / "outputs"
        / f"{repo_name}_migration_context.json"
    )

    builder.save_context(
        context,
        str(context_output),
    )

    print("\n" + "=" * 70)
    print("REPOSITORY CONTEXT")
    print("=" * 70)

    print(
        json.dumps(
            context,
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        f"\nContext saved to:\n"
        f"{context_output}"
    )


if __name__ == "__main__":
    main()