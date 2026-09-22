from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from pipeline.llm.gemini_migrator import (
    GeminiMigrator,
)

from pipeline.llm.migration_service import (
    MigrationService,
)

from pipeline.assembly.repository_assembler import (
    RepositoryAssembler,
)


# ============================================================
# HELPERS
# ============================================================

def load_json(
    path: Path,
) -> Any:

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


def save_json(
    path: Path,
    data: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )


def print_stage(
    title: str,
) -> None:

    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    if len(sys.argv) != 2:

        print(
            "Usage:\n"
            "  python scripts\\run_llm_migration.py "
            "<repository_path>"
        )

        sys.exit(1)

    repository_path = Path(
        sys.argv[1]
    ).resolve()

    if not repository_path.exists():

        print(
            f"ERROR: Repository does not exist: "
            f"{repository_path}"
        )

        sys.exit(1)

    repo_name = repository_path.name

    output_dir = (
        PROJECT_ROOT
        / "outputs"
    )

    # ========================================================
    # Load pre-LLM outputs
    # ========================================================

    prompt_file = (
        output_dir
        / f"{repo_name}_llm_prompts.json"
    )

    context_file = (
        output_dir
        / f"{repo_name}_migration_context.json"
    )

    plan_file = (
        output_dir
        / f"{repo_name}_migration_plan.json"
    )

    features_file = (
        output_dir
        / f"{repo_name}_features.json"
    )

    required_files = [
        prompt_file,
        context_file,
        plan_file,
        features_file,
    ]

    for path in required_files:

        if not path.exists():

            print(
                f"ERROR: Required pre-LLM output "
                f"not found:\n{path}"
            )

            print(
                "\nRun the pre-LLM pipeline first."
            )

            sys.exit(1)

    prompts = load_json(
        prompt_file
    )

    contexts = load_json(
        context_file
    )

    plan = load_json(
        plan_file
    )

    features = load_json(
        features_file
    )

    if not isinstance(
        prompts,
        list,
    ):

        raise RuntimeError(
            "llm_prompts.json must contain a list."
        )

    # ========================================================
    # Initialize LLM
    # ========================================================

    print_stage(
        "AI LEGACY CODE MIGRATION"
    )

    print(
        "LLM MIGRATION ENGINE"
    )

    print(
        f"Repository: "
        f"{repository_path}"
    )

    print()
    print(
        "Provider: Gemini"
    )

    # Model can be controlled using GEMINI_MODEL.
    migrator = GeminiMigrator()

    service = MigrationService(
        llm=migrator
    )

    # ========================================================
    # Migrate files
    # ========================================================

    results = []

    for index, item in enumerate(
        prompts,
        start=1,
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        target_file = (
            item.get("file")
            or ""
        )

        prompt = (
            item.get("prompt")
            or ""
        )

        if not target_file:

            print(
                f"[{index}] SKIP: "
                "missing target file"
            )

            continue

        if not prompt:

            print(
                f"[{index}] SKIP: "
                f"{target_file}: empty prompt"
            )

            continue

        # ----------------------------------------------------
        # Find context
        # ----------------------------------------------------

        context = next(
            (
                ctx
                for ctx in contexts
                if isinstance(
                    ctx,
                    dict,
                )
                and ctx.get(
                    "target",
                    {},
                ).get("file")
                == target_file
            ),
            None,
        )

        if context is None:
            context = {}

        source_code = (
            context
            .get(
                "target",
                {},
            )
            .get(
                "source_code",
                "",
            )
        )

        # ----------------------------------------------------
        # Fallback: read source directly
        # ----------------------------------------------------

        if not source_code:

            source_path = (
                repository_path
                / target_file
            )

            if source_path.exists():

                source_code = (
                    source_path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )
                )

        print()
        print(
            f"[{index}/{len(prompts)}] "
            f"Migrating: {target_file}"
        )

        try:

            result = service.migrate_unit(
                source_code=source_code,
                prompt=prompt,
                repository_context=context,
            )

            result_dict = result.to_dict()

            result_dict[
                "file"
            ] = target_file

            result_dict[
                "migration_order"
            ] = item.get(
                "migration_unit",
                {},
            ).get(
                "order"
            )

            results.append(
                result_dict
            )

            if result.success:

                print(
                    "  [SUCCESS] Migration generated"
                )

                print(
                    f"  Generated code: "
                    f"{len(result.migrated_code)} chars"
                )

            else:

                print(
                    "  [FAILED] "
                    f"{result.error}"
                )

        except Exception as exc:

            print(
                f"  [ERROR] {exc}"
            )

            results.append(
                {
                    "file": target_file,
                    "success": False,
                    "error": str(exc),
                }
            )

    # ========================================================
    # Save results
    # ========================================================

    results_file = (
        output_dir
        / f"{repo_name}_migration_results.json"
    )

    save_json(
        results_file,
        results,
    )

    # ========================================================
    # SAVE LLM-GENERATED FILES
    #
    # These are intermediate outputs only.
    # The final migrated repository is assembled below.
    # ========================================================

    llm_generated_dir = (
        output_dir
        / f"{repo_name}_llm_generated"
    )

    llm_generated_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    successful = 0

    for result in results:

        if not result.get(
            "success"
        ):
            continue

        migrated_code = (
            result.get(
                "migrated_code",
                "",
            )
        )

        target_file = (
            result.get(
                "file"
            )
            or ""
        )

        if not migrated_code or not target_file:
            continue

        output_path = (
            llm_generated_dir
            / target_file
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            migrated_code,
            encoding="utf-8",
        )

        successful += 1

        print(
            f"  [LLM SAVED] {output_path}"
        )

    # ========================================================
    # REPOSITORY ASSEMBLY
    #
    # The migration plan now controls the final repository:
    #
    #   MIGRATE  -> use LLM-generated file
    #   PRESERVE -> copy original file
    #   SKIP     -> exclude from production migrated repo
    #
    # Any other original repository file is automatically
    # preserved by RepositoryAssembler.
    # ========================================================

    print_stage(
        "REPOSITORY ASSEMBLY"
    )

    migrated_dir = (
        output_dir
        / f"{repo_name}_migrated"
    )

    assembler = RepositoryAssembler(
        original_repo=repository_path,
        migration_plan=plan,
        llm_output_dir=llm_generated_dir,
        output_dir=migrated_dir,
    )

    assembly_manifest = assembler.assemble()

    assembly_manifest_file = (
        output_dir
        / f"{repo_name}_assembly_manifest.json"
    )

    save_json(
        assembly_manifest_file,
        assembly_manifest,
    )

    assembly_statistics = (
        assembly_manifest.get(
            "statistics",
            {},
        )
    )

    print(
        f"Assembly status: "
        f"{assembly_manifest.get('status', 'UNKNOWN')}"
    )

    print(
        f"Original files: "
        f"{assembly_statistics.get('original_files', 0)}"
    )

    print(
        f"Migrated files: "
        f"{assembly_statistics.get('migrated_files', 0)}"
    )

    print(
        f"Preserved files: "
        f"{assembly_statistics.get('preserved_files', 0)}"
    )

    print(
        f"Automatically preserved files: "
        f"{assembly_statistics.get('automatically_preserved_files', 0)}"
    )

    print(
        f"Skipped files: "
        f"{assembly_statistics.get('skipped_files', 0)}"
    )

    print(
        f"Assembly errors: "
        f"{assembly_statistics.get('errors', 0)}"
    )

    missing_llm_outputs = (
        assembly_manifest.get(
            "missing_llm_outputs",
            [],
        )
    )

    if missing_llm_outputs:

        print()
        print(
            "[ERROR] Missing LLM outputs:"
        )

        for file_name in missing_llm_outputs:
            print(
                f"  - {file_name}"
            )

    print()
    print(
        "Final repository contents:"
    )

    for item in assembly_manifest.get(
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
            f"{file_name:<40} "
            f"{status}"
        )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print_stage(
        "LLM MIGRATION SUMMARY"
    )

    print(
        f"Migration units: "
        f"{len(prompts)}"
    )

    print(
        f"LLM successful: "
        f"{successful}"
    )

    print(
        f"LLM failed: "
        f"{len(results) - successful}"
    )

    print()
    print(
        f"Results: {results_file}"
    )

    print(
        f"LLM-generated files: "
        f"{llm_generated_dir}"
    )

    print(
        f"Complete migrated repository: "
        f"{migrated_dir}"
    )

    print(
        f"Assembly manifest: "
        f"{assembly_manifest_file}"
    )

    print()
    if assembly_manifest.get("status") == "SUCCESS":
        print(
            "COMPLETE MIGRATED REPOSITORY READY "
            "FOR VERIFICATION"
        )
    else:
        print(
            "MIGRATION/ASSEMBLY FAILED — "
            "DO NOT PROCEED TO VERIFICATION"
        )

    print()
    print(
        "NEXT STAGE: SYNTAX + DEPENDENCY/IMPORT VERIFICATION"
    )


if __name__ == "__main__":
    main()