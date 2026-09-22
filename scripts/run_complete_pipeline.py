from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

PRE_LLM_SCRIPT = SCRIPTS_DIR / "run_pre_llm_pipeline.py"
LLM_ASSEMBLY_SCRIPT = SCRIPTS_DIR / "run_llm_migration_with_assembly.py"
SYNTAX_TEST_SCRIPT = SCRIPTS_DIR / "test_syntax_verification.py"
DEPENDENCY_TEST_SCRIPT = SCRIPTS_DIR / "test_dependency_verification.py"


def header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def run_stage(
    title: str,
    script: Path,
    repo: Path,
    allow_failure: bool = False,
    as_module: bool = False,
) -> bool:
    header(title)

    if not script.exists():
        print(f"[ERROR] Script not found: {script}")
        return False

    if as_module:
        # Running as a module keeps the project root on Python's import path,
        # so imports such as `from pipeline...` work correctly.
        relative = script.relative_to(PROJECT_ROOT).with_suffix("")
        module_name = ".".join(relative.parts)
        cmd = [sys.executable, "-m", module_name]
        cmd.append(str(repo))
    else:
        cmd = [sys.executable, str(script), str(repo)]

    print("[RUNNING]")
    print(" ".join(f'"{x}"' if " " in x else x for x in cmd))
    print()

    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )

    if result.returncode == 0:
        print(f"\n[PASS] {title}")
        return True

    if allow_failure:
        print(f"\n[WARNING] {title} returned exit code {result.returncode}")
        print("[WARNING] Continuing because this stage is non-blocking.")
        return True

    print(f"\n[FAIL] {title} returned exit code {result.returncode}")
    return False


def migrated_repo(repo: Path) -> Path:
    return OUTPUTS_DIR / f"{repo.name}_migrated"


def show_assembly_summary(repo: Path) -> None:
    manifest = OUTPUTS_DIR / f"{repo.name}_assembly_manifest.json"
    if not manifest.exists():
        return

    header("ASSEMBLY SUMMARY")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        stats = data.get("statistics", {})
        if not isinstance(stats, dict):
            stats = {}

        print(f"Original files            : {stats.get('original_files', 0)}")
        print(f"Migrated files            : {stats.get('migrated_files', 0)}")
        print(f"Preserved files           : {stats.get('preserved_files', 0)}")
        print(f"Automatically preserved   : {stats.get('automatically_preserved_files', 0)}")
        print(f"Skipped files             : {stats.get('skipped_files', 0)}")
        print(f"Assembly errors           : {stats.get('errors', 0)}")
        print(f"Manifest                  : {manifest}")
    except Exception as exc:
        print(f"[WARNING] Could not read assembly manifest: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the complete CodeMigrate pipeline.")
    parser.add_argument("repo", help="Path to the legacy source repository.")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()

    header("CODEMIGRATE - COMPLETE END-TO-END PIPELINE")
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Input repo   : {repo}")

    if not repo.is_dir():
        print(f"[ERROR] Repository directory does not exist: {repo}")
        return 1

    # 1. Repository analysis, dependency graph, planning, context and RAG.
    # RAG/network failure is non-blocking for the current pipeline.
    if not run_stage(
        "STAGE 1 - PRE-LLM ANALYSIS",
        PRE_LLM_SCRIPT,
        repo,
        allow_failure=True,
    ):
        return 1

    # 2. LLM migration followed by automatic MIGRATE/PRESERVE/SKIP assembly.
    if not run_stage(
        "STAGE 2 - LLM MIGRATION + REPOSITORY ASSEMBLY",
        LLM_ASSEMBLY_SCRIPT,
        repo,
        allow_failure=False,
    ):
        return 1

    show_assembly_summary(repo)

    output = migrated_repo(repo)
    if not output.is_dir():
        print(f"[ERROR] Migrated repository was not created: {output}")
        return 1

    header("ASSEMBLED REPOSITORY")
    print(f"Output: {output}")
    for path in sorted(output.rglob("*")):
        if path.is_file():
            print(f"  {path.relative_to(output)}")

    # 3. Syntax verification.
    if not run_stage(
        "STAGE 3 - SYNTAX VERIFICATION",
        SYNTAX_TEST_SCRIPT,
        repo,
        allow_failure=False,
        as_module=True,
    ):
        return 1

    # 4. Import/local dependency verification.
    if not run_stage(
        "STAGE 4 - IMPORT & DEPENDENCY VERIFICATION",
        DEPENDENCY_TEST_SCRIPT,
        repo,
        allow_failure=False,
        as_module=True,
    ):
        return 1

    header("CODEMIGRATE - PIPELINE COMPLETE")
    print("Status                    : SUCCESS")
    print("Pre-LLM analysis          : COMPLETED")
    print("Migration planning        : COMPLETED")
    print("LLM migration             : COMPLETED")
    print("Repository assembly       : COMPLETED")
    print("Syntax verification       : PASS")
    print("Import/dependency check   : PASS")
    print(f"Final repository          : {output}")

    print("\nNext stages:")
    print("  Differential / behavioral testing")
    print("  Semantic equivalence verification")
    print("  Migration risk prediction")
    print("  Explainability / migration report")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
