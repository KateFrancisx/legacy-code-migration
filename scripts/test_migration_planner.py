from __future__ import annotations

import json


import sys
from pathlib import Path

# Add project root to Python import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = (
    PROJECT_ROOT / "outputs"
)

from pipeline.dependency import DependencyAnalyzer
from pipeline.planning.migration_planner import MigrationPlanner


def main():

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "  python scripts/test_migration_planner.py "
            "<repo_path>"
        )

        sys.exit(1)

    repo_path = sys.argv[1]

    print("=" * 70)
    print("PYTHON 2 -> PYTHON 3 MIGRATION PLANNER")
    print("=" * 70)

    # --------------------------------------------------------------
    # Dependency analysis
    # --------------------------------------------------------------

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
    # Migration plan
    # --------------------------------------------------------------

    planner = MigrationPlanner(
        result
    )

    plan = planner.build_plan()

    print("\n" + "=" * 70)
    print("MIGRATION ORDER")
    print("=" * 70)

    for index, file_path in enumerate(
        plan["migration_order"],
        start=1
    ):

        unit = next(
            (
                unit
                for unit in plan["units"]
                if unit["file"] == file_path
            ),
            None
        )

        if unit:

            print(
                f"{index}. "
                f"{file_path} "
                f"[{unit['risk']}]"
            )

            if unit[
                "dependencies"
            ]:

                print(
                    "   depends on: "
                    + ", ".join(
                        unit[
                            "dependencies"
                        ]
                    )
                )

            if unit[
                "dependents"
            ]:

                print(
                    "   affects: "
                    + ", ".join(
                        unit[
                            "dependents"
                        ]
                    )
                )

            if unit[
                "migration_reasons"
            ]:

                print(
                    "   reasons: "
                    + ", ".join(
                        unit[
                            "migration_reasons"
                        ]
                    )
                )

    print("\n" + "=" * 70)
    print("MIGRATION PLAN")
    print("=" * 70)

    print(
        json.dumps(
            plan,
            indent=2,
            ensure_ascii=False
        )
    )

    # --------------------------------------------------------------
    # Save
    # --------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    repo_name = (
        Path(repo_path)
        .resolve()
        .name
    )

    output = (
        OUTPUT_DIR
        / f"{repo_name}_migration_plan.json"
    )

    MigrationPlanner.save_plan(
        plan,
        str(output)
    )

    print(
        f"\nMigration plan saved to:\n"
        f"{output}"
    )


if __name__ == "__main__":
    main()