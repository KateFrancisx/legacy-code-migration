import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.dependency import RepositoryContextBuilder


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python scripts/test_repository_context.py "
            "<repo_path> <target_file>"
        )
        sys.exit(1)

    repo_path = sys.argv[1]
    target_file = sys.argv[2]

    plan_path = (
        PROJECT_ROOT
        / "outputs"
        / "python2_migration_test_repo_migration_plan.json"
    )

    if not plan_path.exists():
        print(f"Migration plan not found: {plan_path}")
        sys.exit(1)

    with open(
        plan_path,
        "r",
        encoding="utf-8",
    ) as f:
        plan = json.load(f)

    builder = RepositoryContextBuilder(
        repository_path=repo_path,
        migration_plan=plan,
    )

    context = builder.build(
        target_file
    )

    print("=" * 70)
    print("REPOSITORY MIGRATION CONTEXT")
    print("=" * 70)

    print(
        json.dumps(
            context,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()