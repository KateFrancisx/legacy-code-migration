from __future__ import annotations

import json
import sys
from pathlib import Path

# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORT
# ============================================================

from pipeline.assembly.repository_assembler import (
    RepositoryAssembler,
)



def main() -> None:

    original_repo = (
        Path.home()
        / "Downloads"
        / "python2_migration_test_repo"
    )

    outputs = PROJECT_ROOT / "outputs"

    migration_plan_path = (
        outputs
        / "python2_migration_test_repo_migration_plan.json"
    )

    llm_output_dir = (
        outputs
        / "python2_migration_test_repo_migrated"
    )

    assembled_output_dir = (
        outputs
        / "python2_migration_test_repo_assembled"
    )

    print("=" * 70)
    print("REPOSITORY ASSEMBLER TEST")
    print("=" * 70)

    print()
    print(f"Original repository:")
    print(f"  {original_repo}")

    print()
    print(f"Migration plan:")
    print(f"  {migration_plan_path}")

    print()
    print(f"LLM output:")
    print(f"  {llm_output_dir}")

    print()
    print(f"Assembled repository:")
    print(f"  {assembled_output_dir}")

    if not migration_plan_path.exists():
        raise FileNotFoundError(
            f"Migration plan not found:\n"
            f"{migration_plan_path}"
        )

    if not llm_output_dir.exists():
        raise FileNotFoundError(
            f"LLM output directory not found:\n"
            f"{llm_output_dir}"
        )

    with migration_plan_path.open(
        "r",
        encoding="utf-8",
    ) as f:

        migration_plan = json.load(f)

    assembler = RepositoryAssembler(
        original_repo=original_repo,
        migration_plan=migration_plan,
        llm_output_dir=llm_output_dir,
        output_dir=assembled_output_dir,
    )

    manifest = assembler.assemble()

    manifest_path = (
        outputs
        / "python2_migration_test_repo_assembly_manifest.json"
    )

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 70)
    print("ASSEMBLY RESULT")
    print("=" * 70)

    print()
    print(
        f"Status: "
        f"{manifest.get('status')}"
    )

    statistics = manifest.get(
        "statistics",
        {},
    )

    print()
    print("Statistics:")

    for key, value in statistics.items():
        print(f"  {key}: {value}")

    print()
    print("Files:")

    for item in manifest.get(
        "files",
        [],
    ):

        decision = item.get(
            "decision",
            "UNKNOWN",
        )

        file_name = item.get(
            "file",
            "unknown",
        )

        status = item.get(
            "status",
            "UNKNOWN",
        )

        print(
            f"  [{decision:<8}] "
            f"{file_name:<35} "
            f"{status}"
        )

    print()
    print(
        f"Assembly manifest:"
        f"\n  {manifest_path}"
    )

    print()
    print(
        f"Assembled repository:"
        f"\n  {assembled_output_dir}"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()