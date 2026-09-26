from __future__ import annotations

import argparse
import json
import os
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

SEMANTIC_VERIFIER_MODULE = "pipeline.verification.semantic_verifier"
RISK_ANALYZER_MODULE = "pipeline.verification.risk_analyzer"


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
        relative = script.relative_to(PROJECT_ROOT).with_suffix("")
        module_name = ".".join(relative.parts)
        cmd = [sys.executable, "-m", module_name]
        cmd.append(str(repo))
    else:
        cmd = [sys.executable, str(script), str(repo)]

    print("[RUNNING]")
    print(
        " ".join(
            f'"{x}"' if " " in x else x
            for x in cmd
        )
    )
    print()

    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT),
        },
    )

    if result.returncode == 0:
        print(f"\n[PASS] {title}")
        return True

    if allow_failure:
        print(
            f"\n[WARNING] {title} returned exit code "
            f"{result.returncode}"
        )
        print("[WARNING] Continuing because this stage is non-blocking.")
        return True

    print(
        f"\n[FAIL] {title} returned exit code "
        f"{result.returncode}"
    )
    return False


def run_command_stage(
    title: str,
    command,
    allow_failure: bool = False,
) -> bool:
    header(title)

    print("[RUNNING]")
    print(
        " ".join(
            f'"{x}"' if " " in str(x) else str(x)
            for x in command
        )
    )
    print()

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT),
        },
    )

    if result.returncode == 0:
        print(f"\n[PASS] {title}")
        return True

    if allow_failure:
        print(
            f"\n[WARNING] {title} returned exit code "
            f"{result.returncode}"
        )
        print("[WARNING] Continuing because this stage is non-blocking.")
        return True

    print(
        f"\n[FAIL] {title} returned exit code "
        f"{result.returncode}"
    )
    return False


def migrated_repo(repo: Path) -> Path:
    return OUTPUTS_DIR / f"{repo.name}_migrated"


def show_assembly_summary(repo: Path) -> None:
    manifest = OUTPUTS_DIR / f"{repo.name}_assembly_manifest.json"

    if not manifest.exists():
        return

    header("ASSEMBLY SUMMARY")

    try:
        data = json.loads(
            manifest.read_text(
                encoding="utf-8"
            )
        )

        stats = data.get(
            "statistics",
            {}
        )

        if not isinstance(
            stats,
            dict,
        ):
            stats = {}

        print(
            f"Original files            : "
            f"{stats.get('original_files', 0)}"
        )

        print(
            f"Migrated files            : "
            f"{stats.get('migrated_files', 0)}"
        )

        print(
            f"Preserved files           : "
            f"{stats.get('preserved_files', 0)}"
        )

        print(
            f"Automatically preserved   : "
            f"{stats.get('automatically_preserved_files', 0)}"
        )

        print(
            f"Skipped files             : "
            f"{stats.get('skipped_files', 0)}"
        )

        print(
            f"Assembly errors           : "
            f"{stats.get('errors', 0)}"
        )

        print(
            f"Manifest                  : "
            f"{manifest}"
        )

    except Exception as exc:
        print(
            f"[WARNING] Could not read assembly manifest: "
            f"{exc}"
        )


def show_semantic_summary() -> None:
    report_path = (
        OUTPUTS_DIR
        / "semantic_verification_report.json"
    )

    if not report_path.exists():
        print(
            "[WARNING] Semantic verification report "
            "was not found."
        )
        return

    try:
        data = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )

        summary = data.get(
            "summary",
            {}
        )

        header("SEMANTIC VERIFICATION SUMMARY")

        print(
            "Existing tests equivalent : "
            f"{summary.get('existing_tests_equivalent')}"
        )

        print(
            "Behavioral cases          : "
            f"{summary.get('behavioral_cases', 0)}"
        )

        print(
            "Behaviorally equivalent   : "
            f"{summary.get('behavioral_equivalent', 0)}"
        )

        print(
            "Semantic differences      : "
            f"{summary.get('behavioral_semantic_differences', 0)}"
        )

        print(
            f"Report                    : {report_path}"
        )

    except Exception as exc:
        print(
            f"[WARNING] Could not read semantic report: "
            f"{exc}"
        )


def show_risk_summary() -> None:
    report_path = (
        OUTPUTS_DIR
        / "risk_report.json"
    )

    if not report_path.exists():
        print(
            "[WARNING] Risk report was not found."
        )
        return

    try:
        data = json.loads(
            report_path.read_text(
                encoding="utf-8"
            )
        )

        files = data.get(
            "files",
            {}
        )

        header("MIGRATION RISK SUMMARY")

        if not files:
            print("No file-level risk results found.")
            return

        for file_name, result in files.items():
            print(
                f"{file_name:<20} "
                f"risk={result.get('risk', 'UNKNOWN')}"
            )

        print(
            f"\nReport                    : {report_path}"
        )

    except Exception as exc:
        print(
            f"[WARNING] Could not read risk report: "
            f"{exc}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the complete CodeMigrate pipeline."
    )

    parser.add_argument(
        "repo",
        help="Path to the legacy source repository.",
    )

    args = parser.parse_args()

    repo = Path(
        args.repo
    ).expanduser().resolve()

    header(
        "CODEMIGRATE - COMPLETE END-TO-END PIPELINE"
    )

    print(
        f"Project root : {PROJECT_ROOT}"
    )

    print(
        f"Input repo   : {repo}"
    )

    if not repo.is_dir():
        print(
            f"[ERROR] Repository directory does not exist: "
            f"{repo}"
        )
        return 1

    # ---------------------------------------------------------
    # 1. Repository analysis, dependency graph, planning,
    #    migration context and RAG.
    # ---------------------------------------------------------

    if not run_stage(
        "STAGE 1 - PRE-LLM ANALYSIS",
        PRE_LLM_SCRIPT,
        repo,
        allow_failure=True,
    ):
        return 1

    # ---------------------------------------------------------
    # 2. LLM migration followed by automatic
    #    MIGRATE/PRESERVE/SKIP repository assembly.
    # ---------------------------------------------------------

    if not run_stage(
        "STAGE 2 - LLM MIGRATION + REPOSITORY ASSEMBLY",
        LLM_ASSEMBLY_SCRIPT,
        repo,
        allow_failure=False,
    ):
        return 1

    show_assembly_summary(
        repo
    )

    output = migrated_repo(
        repo
    )

    if not output.is_dir():
        print(
            f"[ERROR] Migrated repository was not created: "
            f"{output}"
        )
        return 1

    header(
        "ASSEMBLED REPOSITORY"
    )

    print(
        f"Output: {output}"
    )

    for path in sorted(
        output.rglob("*")
    ):
        if path.is_file():
            print(
                f"  {path.relative_to(output)}"
            )

    # ---------------------------------------------------------
    # 3. Syntax verification.
    # ---------------------------------------------------------

    if not run_stage(
        "STAGE 3 - SYNTAX VERIFICATION",
        SYNTAX_TEST_SCRIPT,
        repo,
        allow_failure=False,
        as_module=True,
    ):
        return 1

    # ---------------------------------------------------------
    # 4. Import/local dependency verification.
    # ---------------------------------------------------------

    if not run_stage(
        "STAGE 4 - IMPORT & DEPENDENCY VERIFICATION",
        DEPENDENCY_TEST_SCRIPT,
        repo,
        allow_failure=False,
        as_module=True,
    ):
        return 1

    # ---------------------------------------------------------
    # 5. Differential + behavioral + semantic verification.
    #
    # This stage:
    #   - runs existing repository tests
    #   - discovers migrated callables
    #   - generates behavioral cases using the LLM
    #   - executes Python 2 and Python 3
    #   - compares their behavior
    #   - writes semantic_verification_report.json
    # ---------------------------------------------------------

    if not run_command_stage(
        "STAGE 5 - DIFFERENTIAL / SEMANTIC VERIFICATION",
        [
            sys.executable,
            "-m",
            SEMANTIC_VERIFIER_MODULE,
            str(OUTPUTS_DIR),
            "--report",
            str(
                OUTPUTS_DIR
                / "semantic_verification_report.json"
            ),
        ],
        allow_failure=False,
    ):
        return 1

    show_semantic_summary()

    # ---------------------------------------------------------
    # 6. Migration risk prediction.
    #
    # Consumes semantic_verification_report.json and writes
    # risk_report.json.
    # ---------------------------------------------------------

    semantic_report = (
        OUTPUTS_DIR
        / "semantic_verification_report.json"
    )

    risk_report = (
        OUTPUTS_DIR
        / "risk_report.json"
    )

    if not run_command_stage(
        "STAGE 6 - MIGRATION RISK PREDICTION",
        [
            sys.executable,
            "-m",
            RISK_ANALYZER_MODULE,
            str(OUTPUTS_DIR),
            "--semantic-report",
            str(semantic_report),
            "--report",
            str(risk_report),
        ],
        allow_failure=False,
    ):
        return 1

    show_risk_summary()

    # ---------------------------------------------------------
    # FINAL PIPELINE SUMMARY
    # ---------------------------------------------------------

    header(
        "CODEMIGRATE - PIPELINE COMPLETE"
    )

    print(
        "Status                    : SUCCESS"
    )

    print(
        "Pre-LLM analysis          : COMPLETED"
    )

    print(
        "Migration planning        : COMPLETED"
    )

    print(
        "LLM migration             : COMPLETED"
    )

    print(
        "Repository assembly       : COMPLETED"
    )

    print(
        "Syntax verification      : PASS"
    )

    print(
        "Import/dependency check  : PASS"
    )

    print(
        "Differential testing     : COMPLETED"
    )

    print(
        "Semantic verification    : COMPLETED"
    )

    print(
        "Risk prediction          : COMPLETED"
    )

    print(
        f"Final repository          : {output}"
    )

    print(
        f"Semantic report           : "
        f"{semantic_report}"
    )

    print(
        f"Risk report               : "
        f"{risk_report}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )