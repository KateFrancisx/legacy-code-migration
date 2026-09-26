from __future__ import annotations

import os

import json
import shutil
import subprocess
import sys
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# PROJECT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_ROOT = PROJECT_ROOT / "outputs"
UI_JOB_ROOT = OUTPUT_ROOT / "ui_jobs"

UI_JOB_ROOT.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="CodeMigrate API",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# IN-MEMORY JOB STORE
# ============================================================

JOBS: dict[str, dict[str, Any]] = {}

PIPELINE_LOCK = threading.Lock()


# ============================================================
# PIPELINE STAGES
# ============================================================

STAGES = [
    "scan",
    "version",
    "selection",
    "extraction",
    "embeddings",
    "dependency",
    "planning",
    "context",
    "rag",
    "prompt",
    "llm",
    "assembly",
    "syntax",
    "dependency_verification",
    "test_generation",
    "differential_testing",
    "behavioral_verification",
    "semantic_equivalence",
    "risk_analysis",
    "explainability",
    "final_report",
]


STAGE_TITLES = {
    "scan": "Repository Scan",
    "version": "Version Detection",
    "selection": "Migration Selection",
    "extraction": "Code Extraction",
    "embeddings": "CodeBERT Embeddings",
    "dependency": "Dependency Graph",
    "planning": "Migration Planning",
    "context": "Repository Context",
    "rag": "RAG Retrieval",
    "prompt": "Prompt Construction",
    "llm": "LLM Migration",
    "assembly": "Repository Assembly",
    "syntax": "Syntax Verification",
    "dependency_verification": "Dependency Verification",
    "test_generation": "Test Generation",
    "differential_testing": "Differential Testing",
    "behavioral_verification": "Behavioral Verification",
    "semantic_equivalence": "Semantic Equivalence",
    "risk_analysis": "Risk Analysis",
    "explainability": "Explainability",
    "final_report": "Final Migration Report",
}


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path) -> Any:
    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)
    except Exception:
        return None


def update_stage(
    job_id: str,
    stage: str,
    status: str,
) -> None:

    job = JOBS.get(job_id)

    if not job:
        return

    job["stage_status"][stage] = status
    job["current_stage"] = stage


def set_all_pending(job_id: str) -> None:

    job = JOBS[job_id]

    job["stage_status"] = {
        stage: "pending"
        for stage in STAGES
    }


def output_file(
    repo_name: str,
    suffix: str,
) -> Path:

    return (
        OUTPUT_ROOT
        / f"{repo_name}_{suffix}.json"
    )


def clean_previous_outputs(repo_name: str) -> None:

    suffixes = [
        "scan",
        "version_manifest",
        "migration_selection",
        "features",
        "embedded_features",
        "dependency_graph",
        "migration_plan",
        "migration_context",
        "rag_results",
        "llm_prompts",
        "pre_llm_summary",
        "migration_results",
        "assembly_manifest",
        "syntax_verification",
        "dependency_verification",
    ]

    for suffix in suffixes:

        path = output_file(
            repo_name,
            suffix,
        )

        if path.exists():
            path.unlink()

    for report_name in [
        "semantic_verification_report.json",
        "risk_report.json",
    ]:
        report_path = OUTPUT_ROOT / report_name

        if report_path.exists():
            report_path.unlink()

    migrated_dir = (
        OUTPUT_ROOT
        / f"{repo_name}_migrated"
    )

    if migrated_dir.exists():
        shutil.rmtree(migrated_dir)


def safe_json_size(value: Any) -> int:

    try:
        return len(
            json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )
        )
    except Exception:
        return 0



# ============================================================
# STAGE / REPORT HELPERS
# ============================================================

def make_stage_result(
    stage: str,
    status: str,
    data: Any = None,
    message: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "title": STAGE_TITLES.get(stage, stage),
        "status": status,
        "available": data is not None,
        "message": message,
        "error": error,
        "data": data,
    }


def stage_counts(stage_status: dict[str, str]) -> dict[str, int]:
    counts = {
        "total": len(STAGES),
        "completed": 0,
        "running": 0,
        "failed": 0,
        "pending": 0,
    }
    for status in stage_status.values():
        if status in counts:
            counts[status] += 1
    counts["not_completed"] = (
        counts["running"] + counts["failed"] + counts["pending"]
    )
    return counts


def derive_failure_message(
    job: dict[str, Any],
    fallback: str,
) -> str:
    logs = job.get("logs", [])
    failure_lines = [
        line for line in logs
        if "[FAIL]" in line
        or "Traceback" in line
        or "Error:" in line
        or "Exception" in line
    ]

    if failure_lines:
        # Keep the most useful recent lines without exposing hundreds of
        # log lines in the job error field.
        recent = failure_lines[-5:]
        return (
            fallback
            + " "
            + " | ".join(recent)
        )

    return fallback


def build_explainability(
    semantic_report: Any,
    risk_report: Any,
    syntax_report: Any,
    dependency_report: Any,
    stage_status: dict[str, str],
    error: str | None = None,
) -> dict[str, Any]:
    evidence = []

    for source, value in [
        ("syntax_verification", syntax_report),
        ("dependency_verification", dependency_report),
        ("semantic_verification", semantic_report),
        ("risk_analysis", risk_report),
    ]:
        if value is not None:
            evidence.append({
                "source": source,
                "available": True,
                "result": value,
            })

    reasons = []

    if stage_status.get("syntax") == "failed":
        reasons.append("Syntax verification failed.")

    if stage_status.get("dependency_verification") == "failed":
        reasons.append("Dependency verification failed.")

    if stage_status.get("differential_testing") == "failed":
        reasons.append(
            "Differential / semantic verification failed before "
            "downstream verification and risk analysis completed."
        )

    if stage_status.get("risk_analysis") == "failed":
        reasons.append("Risk analysis failed.")

    if semantic_report is None:
        reasons.append("No semantic verification report is available.")

    if risk_report is None:
        reasons.append("No risk report is available.")

    if error:
        reasons.append(error)

    return {
        "status": "available" if evidence else "not_available",
        "summary": (
            "Evidence assembled from the actual verification and "
            "risk-analysis outputs."
            if evidence
            else
            "Explainability evidence is unavailable because the "
            "required downstream outputs were not produced."
        ),
        "reasons": reasons,
        "evidence": evidence,
    }


def build_final_report(
    repository_name: str,
    status: str,
    error: str | None,
    stage_status: dict[str, str],
    statistics: dict[str, Any],
    results: dict[str, Any],
) -> dict[str, Any]:
    completed = [
        stage for stage in STAGES
        if stage_status.get(stage) == "completed"
    ]
    failed = [
        stage for stage in STAGES
        if stage_status.get(stage) == "failed"
    ]
    running = [
        stage for stage in STAGES
        if stage_status.get(stage) == "running"
    ]
    pending = [
        stage for stage in STAGES
        if stage_status.get(stage) == "pending"
    ]

    return {
        "repository": repository_name,
        "pipeline_status": status,
        "summary": {
            "message": (
                "Migration pipeline completed successfully."
                if status == "completed"
                else
                "Migration pipeline stopped before all stages completed."
            ),
            "error": error,
        },
        "statistics": statistics,
        "stage_summary": {
            "total": len(STAGES),
            "completed": len(completed),
            "failed": len(failed),
            "running": len(running),
            "pending": len(pending),
        },
        "completed_stages": completed,
        "failed_stages": failed,
        "running_stages": running,
        "pending_stages": pending,
        "verification": {
            "syntax": results.get("syntax"),
            "dependency_verification": results.get(
                "dependency_verification"
            ),
            "test_generation": results.get("test_generation"),
            "differential_testing": results.get(
                "differential_testing"
            ),
            "behavioral_verification": results.get(
                "behavioral_verification"
            ),
            "semantic_equivalence": results.get(
                "semantic_equivalence"
            ),
            "risk_analysis": results.get("risk_analysis"),
        },
        "explainability": results.get("explainability"),
    }


def populate_derived_results(
    results: dict[str, Any],
    stage_status: dict[str, str],
    repository_name: str,
    pipeline_status: str,
    error: str | None = None,
) -> dict[str, Any]:
    semantic_report = results.get("semantic_equivalence")
    risk_report = results.get("risk_analysis")

    # These four UI stages are views over the single Stage 5 command.
    for stage, message in {
        "test_generation": (
            "Behavioral test generation is part of the "
            "semantic-verification stage."
        ),
        "differential_testing": (
            "Differential execution is part of the "
            "semantic-verification stage."
        ),
        "behavioral_verification": (
            "Behavioral verification is part of the "
            "semantic-verification stage."
        ),
    }.items():
        current = stage_status.get(stage, "pending")

        if semantic_report is not None:
            results[stage] = make_stage_result(
                stage, "completed", semantic_report, message
            )
        elif current == "failed":
            results[stage] = make_stage_result(
                stage, "failed", message=message, error=error
            )
        elif current == "running":
            results[stage] = make_stage_result(
                stage, "running", message=message
            )
        else:
            results[stage] = make_stage_result(
                stage,
                "pending",
                message=(
                    "Not reached because an earlier pipeline stage "
                    "stopped execution."
                ),
            )

    if semantic_report is None:
        results["semantic_equivalence"] = make_stage_result(
            "semantic_equivalence",
            stage_status.get("semantic_equivalence", "pending"),
            message="No semantic verification report was produced.",
            error=error if stage_status.get(
                "differential_testing"
            ) == "failed" else None,
        )

    if risk_report is None:
        results["risk_analysis"] = make_stage_result(
            "risk_analysis",
            stage_status.get("risk_analysis", "pending"),
            message=(
                "Risk analysis was not reached because the required "
                "semantic verification did not complete."
                if stage_status.get("risk_analysis") == "pending"
                else "No risk report was produced."
            ),
            error=error if stage_status.get(
                "risk_analysis"
            ) == "failed" else None,
        )

    results["explainability"] = build_explainability(
        semantic_report=semantic_report,
        risk_report=risk_report,
        syntax_report=results.get("syntax"),
        dependency_report=results.get("dependency_verification"),
        stage_status=stage_status,
        error=error,
    )

    results["final_report"] = build_final_report(
        repository_name=repository_name,
        status=pipeline_status,
        error=error,
        stage_status=stage_status,
        statistics=results.get("statistics", {}),
        results=results,
    )

    return results

# ============================================================
# READ PIPELINE RESULTS
# ============================================================

def collect_results(
    repo_name: str,
    repository_path: Path,
) -> dict[str, Any]:

    results: dict[str, Any] = {}

    # --------------------------------------------------------
    # Scan
    # --------------------------------------------------------

    results["scan"] = load_json(
        output_file(
            repo_name,
            "scan",
        )
    )

    # --------------------------------------------------------
    # Version detection
    # --------------------------------------------------------

    results["version"] = load_json(
        output_file(
            repo_name,
            "version_manifest",
        )
    )

    # --------------------------------------------------------
    # Migration selection
    # --------------------------------------------------------

    results["selection"] = load_json(
        output_file(
            repo_name,
            "migration_selection",
        )
    )

    # --------------------------------------------------------
    # Extraction
    # --------------------------------------------------------

    results["extraction"] = load_json(
        output_file(
            repo_name,
            "features",
        )
    )

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    embeddings = load_json(
        output_file(
            repo_name,
            "embedded_features",
        )
    )

    if isinstance(embeddings, list):

        # Do NOT send huge 768-dimensional vectors
        # to the browser.
        results["embeddings"] = {
            "records": len(embeddings),
            "dimension": 768 if embeddings else 0,
            "model": "microsoft/codebert-base",
        }

    else:
        results["embeddings"] = embeddings

    # --------------------------------------------------------
    # Dependency
    # --------------------------------------------------------

    results["dependency"] = load_json(
        output_file(
            repo_name,
            "dependency_graph",
        )
    )

    # --------------------------------------------------------
    # Planning
    # --------------------------------------------------------

    results["planning"] = load_json(
        output_file(
            repo_name,
            "migration_plan",
        )
    )

    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    results["context"] = load_json(
        output_file(
            repo_name,
            "migration_context",
        )
    )

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    results["rag"] = load_json(
        output_file(
            repo_name,
            "rag_results",
        )
    )

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------

    prompts = load_json(
        output_file(
            repo_name,
            "llm_prompts",
        )
    )

    if isinstance(prompts, list):

        results["prompt"] = {
            "count": len(prompts),
            "prompts": prompts,
        }

    else:
        results["prompt"] = prompts

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------

    migration_results = load_json(
        output_file(
            repo_name,
            "migration_results",
        )
    )

    if isinstance(
        migration_results,
        list,
    ):

        enriched = []

        for item in migration_results:

            if not isinstance(
                item,
                dict,
            ):
                continue

            item = dict(item)

            target_file = (
                item.get("file")
                or ""
            )

            # Source code
            source_code = ""

            if target_file:

                source_path = (
                    repository_path
                    / target_file
                )

                if source_path.exists():

                    try:
                        source_code = (
                            source_path.read_text(
                                encoding="utf-8",
                                errors="ignore",
                            )
                        )
                    except Exception:
                        source_code = ""

            item["source_code"] = source_code

            enriched.append(item)

        results["llm"] = enriched

    else:

        results["llm"] = migration_results


    # --------------------------------------------------------
    # Repository Assembly
    # --------------------------------------------------------

    results["assembly"] = load_json(
        output_file(
            repo_name,
            "assembly_manifest",
        )
    )

    # --------------------------------------------------------
    # Syntax Verification
    # --------------------------------------------------------

    results["syntax"] = load_json(
        output_file(
            repo_name,
            "syntax_verification",
        )
    )

    # --------------------------------------------------------
    # Dependency Verification
    # --------------------------------------------------------

    results["dependency_verification"] = load_json(
        output_file(
            repo_name,
            "dependency_verification",
        )
    )

    # --------------------------------------------------------
    # Semantic Verification
    # --------------------------------------------------------

    semantic_report = OUTPUT_ROOT / "semantic_verification_report.json"

    results["semantic_equivalence"] = load_json(
        semantic_report
    )

    # --------------------------------------------------------
    # Risk Analysis
    # --------------------------------------------------------

    risk_report = OUTPUT_ROOT / "risk_report.json"

    results["risk_analysis"] = load_json(
        risk_report
    )


    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    scan = results.get("scan")

    files = 0

    if isinstance(scan, dict):

        file_list = (
            scan.get("files")
            or scan.get("file_records")
            or []
        )

        if isinstance(
            file_list,
            list,
        ):
            files = len(file_list)

    selection = results.get(
        "selection"
    )

    candidates = 0

    if isinstance(
        selection,
        dict,
    ):

        targets = (
            selection.get("targets")
            or []
        )

        if isinstance(
            targets,
            list,
        ):
            candidates = len(targets)

    extraction = results.get(
        "extraction"
    )

    functions = (
        len(extraction)
        if isinstance(
            extraction,
            list,
        )
        else 0
    )

    rag = results.get("rag")

    rag_queries = 0

    if isinstance(
        rag,
        list,
    ):
        rag_queries = len(rag)

    elif isinstance(
        rag,
        dict,
    ):
        rag_queries = len(rag)

    results["statistics"] = {
        "files": files,
        "candidates": candidates,
        "functions": functions,
        "rag_queries": rag_queries,
    }

    return results


# ============================================================
# PARSE PIPELINE OUTPUT
# ============================================================

def process_output_line(
    job_id: str,
    line: str,
    llm_phase: bool = False,
) -> None:

    text = line.strip()

    if not text:
        return

    job = JOBS.get(job_id)

    if not job:
        return

    job["logs"].append(text)

    # Keep browser response reasonably small.
    if len(job["logs"]) > 100:
        job["logs"] = job["logs"][-100:]

    # --------------------------------------------------------
    # Stage detection
    # --------------------------------------------------------

    stage_map = {
        # Pre-LLM
        "1. REPOSITORY SCANNING": "scan",
        "2. PYTHON VERSION DETECTION": "version",
        "3. MIGRATION JOB SELECTION": "selection",
        "4. CODE EXTRACTION / STATIC FEATURES": "extraction",
        "5. CODEBERT EMBEDDINGS": "embeddings",
        "6. DEPENDENCY GRAPH": "dependency",
        "7. MIGRATION PLANNING": "planning",
        "8. REPOSITORY CONTEXT": "context",
        "9. RAG MIGRATION KNOWLEDGE RETRIEVAL": "rag",
        "10. FINAL LLM PROMPTS": "prompt",  

        # LLM migration
        "LLM MIGRATION ENGINE": "llm",

        # Repository assembly
        "REPOSITORY ASSEMBLY": "assembly",

        # Verification
        "CODEMIGRATE - SYNTAX VERIFICATION": "syntax",
        "CODEMIGRATE - IMPORT & DEPENDENCY VERIFICATION":
            "dependency_verification",

        # Semantic / behavioral verification
        "STAGE 5 - DIFFERENTIAL / SEMANTIC VERIFICATION":
            "differential_testing",

        # Risk analysis
        "STAGE 6 - MIGRATION RISK PREDICTION":
            "risk_analysis",
    }


    # --------------------------------------------------------
    # Explicit stage completion / failure detection
    # --------------------------------------------------------

    pass_map = {
        "STAGE 3 - SYNTAX VERIFICATION":
            "syntax",

        "STAGE 4 - IMPORT & DEPENDENCY VERIFICATION":
            "dependency_verification",
    }

    fail_map = {
        "STAGE 3 - SYNTAX VERIFICATION":
            "syntax",

        "STAGE 4 - IMPORT & DEPENDENCY VERIFICATION":
            "dependency_verification",

        "STAGE 5 - DIFFERENTIAL / SEMANTIC VERIFICATION":
            "differential_testing",

        "STAGE 6 - MIGRATION RISK PREDICTION":
            "risk_analysis",
    }

    if "[PASS]" in text:

        for title, stage in pass_map.items():

            if title in text:

                update_stage(
                    job_id,
                    stage,
                    "completed",
                )

                return

    if "[FAIL]" in text:

        for title, stage in fail_map.items():

            if title in text:

                update_stage(
                    job_id,
                    stage,
                    "failed",
                )

                return

    # --------------------------------------------------------
    # Detect current stage
    # --------------------------------------------------------

    detected_stage = None

    for title, stage in stage_map.items():

        if title in text:
            detected_stage = stage
            break

    if detected_stage is not None:

        stage_index = STAGES.index(
            detected_stage
        )

        # Mark previous stages as completed.
        for previous in STAGES[:stage_index]:

            if (
                job["stage_status"].get(previous)
                not in ["failed"]
            ):
                job["stage_status"][
                    previous
                ] = "completed"

        # Mark current stage as running.
        update_stage(
            job_id,
            detected_stage,
            "running",
        )

        return

    # --------------------------------------------------------
    # LLM migration progress
    # --------------------------------------------------------

    if llm_phase:

        if (
            text.startswith("[")
            and "] Migrating:" in text
        ):
            update_stage(
                job_id,
                "llm",
                "running",
            )

        if "[SUCCESS]" in text:

            update_stage(
                job_id,
                "llm",
                "running",
            )

        return

    # --------------------------------------------------------
    # Verification sub-stage detection
    # --------------------------------------------------------

    if (
        "Generating Groq cases for:" in text
        or "GROQ REQUEST" in text
    ):
        update_stage(job_id, "test_generation", "running")

    if "GROQ PARSED CASE COUNT:" in text:
        update_stage(job_id, "test_generation", "completed")

    # Stage 5 performs several kinds of verification together.
    # We expose them separately in the UI, but they are executed
    # by the same semantic-verification command.

    if (
        "Behavioral equivalence" in text
        or "Behavioral cases" in text
    ):
        update_stage(
            job_id,
            "behavioral_verification",
            "running",
        )

    if (
        "Semantic differences" in text
        or "Semantic verification" in text
    ):
        update_stage(
            job_id,
            "semantic_equivalence",
            "running",
        )

# ============================================================
# RUN PIPELINE
# ============================================================

def run_pipeline(
    job_id: str,
    repository_path: Path,
) -> None:

    job = JOBS[job_id]
    repo_name = repository_path.name

    try:
        with PIPELINE_LOCK:
            job["status"] = "running"

            clean_previous_outputs(repo_name)

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            command = [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "scripts"
                    / "run_complete_pipeline.py"
                ),
                str(repository_path),
            ]

            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )

            assert process.stdout is not None

            for line in process.stdout:
                process_output_line(
                    job_id,
                    line,
                    llm_phase=False,
                )

            return_code = process.wait()

            # Always collect artifacts that were produced, even when
            # a later stage fails.
            job["results"] = collect_results(
                repo_name,
                repository_path,
            )

            job["statistics"] = job["results"].get(
                "statistics",
                {},
            )

            if return_code != 0:
                raise RuntimeError(
                    "Complete migration pipeline failed. "
                    "Check the pipeline logs for the failed stage."
                )

            # The complete executable pipeline currently reaches
            # Risk Analysis. Explainability and Final Report are
            # dashboard-derived views.
            actual_completed = [
                "scan",
                "version",
                "selection",
                "extraction",
                "embeddings",
                "dependency",
                "planning",
                "context",
                "rag",
                "prompt",
                "llm",
                "assembly",
                "syntax",
                "dependency_verification",
            ]

            if job["results"].get(
                "semantic_equivalence"
            ) is not None:
                actual_completed.extend([
                    "test_generation",
                    "differential_testing",
                    "behavioral_verification",
                    "semantic_equivalence",
                ])

            if job["results"].get("risk_analysis") is not None:
                actual_completed.append("risk_analysis")

            for stage in actual_completed:
                if job["stage_status"].get(stage) != "failed":
                    job["stage_status"][stage] = "completed"

            job["status"] = "completed"

            if job["results"].get("risk_analysis") is not None:
                job["current_stage"] = "risk_analysis"
            elif job["results"].get(
                "semantic_equivalence"
            ) is not None:
                job["current_stage"] = "semantic_equivalence"
            else:
                job["current_stage"] = "dependency_verification"

            job["results"] = populate_derived_results(
                results=job["results"],
                stage_status=job["stage_status"],
                repository_name=repo_name,
                pipeline_status=job["status"],
            )

            # These are dashboard-derived reporting stages.
            job["stage_status"]["explainability"] = "completed"
            job["stage_status"]["final_report"] = "completed"

            # Rebuild the report after reporting stages receive their
            # final statuses so the report itself is internally consistent.
            job["results"]["final_report"] = build_final_report(
                repository_name=repo_name,
                status=job["status"],
                error=None,
                stage_status=job["stage_status"],
                statistics=job["statistics"],
                results=job["results"],
            )

    except Exception as exc:
        job["status"] = "failed"
        error_text = derive_failure_message(
            job,
            str(exc).strip(),
        )
        job["error"] = error_text

        current = job.get("current_stage")

        if current in STAGES:
            job["stage_status"][current] = "failed"

        # Stages after a failed stage were not executed.
        if current == "differential_testing":
            for stage in [
                "behavioral_verification",
                "semantic_equivalence",
                "risk_analysis",
                "explainability",
                "final_report",
            ]:
                if job["stage_status"].get(stage) != "failed":
                    job["stage_status"][stage] = "pending"

        elif current == "risk_analysis":
            for stage in [
                "explainability",
                "final_report",
            ]:
                if job["stage_status"].get(stage) != "failed":
                    job["stage_status"][stage] = "pending"

        # collect_results() normally already ran before the exception,
        # but this also covers exceptions raised before collection.
        try:
            job["results"] = collect_results(
                repo_name,
                repository_path,
            )

            job["statistics"] = job["results"].get(
                "statistics",
                {},
            )

            job["results"] = populate_derived_results(
                results=job["results"],
                stage_status=job["stage_status"],
                repository_name=repo_name,
                pipeline_status=job["status"],
                error=error_text,
            )

            # The dashboard can still produce a failure report even
            # when the migration pipeline stops early.
            job["stage_status"]["final_report"] = "completed"

            if job["results"].get("explainability", {}).get(
                "status"
            ) == "available":
                job["stage_status"]["explainability"] = "completed"
            else:
                job["stage_status"]["explainability"] = "pending"

            job["results"]["final_report"] = build_final_report(
                repository_name=repo_name,
                status=job["status"],
                error=error_text,
                stage_status=job["stage_status"],
                statistics=job["statistics"],
                results=job["results"],
            )

        except Exception as result_error:
            job["results"] = {}
            job["statistics"] = {}
            job["error"] = (
                f"{error_text}; "
                f"Could not collect partial results: "
                f"{result_error}"
            )

            job["results"]["final_report"] = {
                "repository": repo_name,
                "pipeline_status": "failed",
                "summary": {
                    "message": (
                        "The migration pipeline failed before "
                        "complete result collection."
                    ),
                    "error": job["error"],
                },
            }
            job["stage_status"]["final_report"] = "completed"

        # Guarantee that the failed stage has a visible result.
        if current in STAGES:
            existing = job["results"].get(current)

            if existing is None:
                job["results"][current] = make_stage_result(
                    current,
                    "failed",
                    message=(
                        f"{STAGE_TITLES.get(current, current)} "
                        "failed before producing its report."
                    ),
                    error=error_text,
                )
            elif isinstance(existing, dict):
                existing.setdefault("status", "failed")
                existing.setdefault("error", error_text)

        # Always produce a readable final report.
        job["results"]["final_report"] = build_final_report(
            repository_name=repo_name,
            status=job["status"],
            error=error_text,
            stage_status=job["stage_status"],
            statistics=job["statistics"],
            results=job["results"],
        )



# ============================================================
# DOWNLOAD FINAL MIGRATED REPOSITORY
# ============================================================

@app.get("/api/jobs/{job_id}/download")
def download_migrated_repository(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found.")

    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="The migrated repository is not ready yet.")

    repo_name = job.get("repository_name")
    if not repo_name:
        raise HTTPException(status_code=404, detail="Repository name is unavailable.")

    migrated_dir = OUTPUT_ROOT / f"{repo_name}_migrated"
    if not migrated_dir.exists() or not migrated_dir.is_dir():
        raise HTTPException(status_code=404, detail="Migrated repository directory was not found.")

    archive_base = OUTPUT_ROOT / f"{repo_name}_migrated_download"
    archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=migrated_dir))

    return FileResponse(
        path=str(archive_path),
        media_type="application/zip",
        filename=f"{repo_name}_migrated.zip",
    )

# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health() -> dict[str, str]:

    return {
        "status": "ok",
        "service": "CodeMigrate API",
    }


# ============================================================
# START MIGRATION
# ============================================================

@app.post("/api/migrate")
async def start_migration(
    file: UploadFile = File(...),
) -> dict[str, Any]:

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file provided.",
        )

    if not file.filename.lower().endswith(
        ".zip"
    ):

        raise HTTPException(
            status_code=400,
            detail="Only ZIP repositories are supported.",
        )

    job_id = uuid.uuid4().hex[:12]

    original_name = Path(
        file.filename
    ).stem

    job_dir = (
        UI_JOB_ROOT
        / job_id
    )

    extract_dir = (
        job_dir
        / "repository"
    )

    job_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    extract_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    zip_path = (
        job_dir
        / file.filename
    )

    try:

        with zip_path.open(
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer,
            )

        # --------------------------------------------
        # Extract ZIP
        # --------------------------------------------

        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as archive:

            archive.extractall(
                extract_dir
            )

    except zipfile.BadZipFile:

        shutil.rmtree(
            job_dir,
            ignore_errors=True,
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid ZIP file.",
        )

    # --------------------------------------------
    # Find repository root
    # --------------------------------------------

    children = [
        p
        for p in extract_dir.iterdir()
        if p.name != "__MACOSX"
    ]

    if len(children) == 1 and children[0].is_dir():

        repository_path = children[0]

    else:

        repository_path = (
            extract_dir
            / original_name
        )

        repository_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        for child in children:

            if child == repository_path:
                continue

            destination = (
                repository_path
                / child.name
            )

            shutil.move(
                str(child),
                str(destination),
            )

    repo_name = repository_path.name

    # --------------------------------------------
    # Create job
    # --------------------------------------------

    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "repository_name": repo_name,
        "original_filename": file.filename,
        "current_stage": "scan",
        "stage_status": {
            stage: "pending"
            for stage in STAGES
        },
        "statistics": {},
        "results": {},
        "logs": [],
        "error": None,
    }

    # --------------------------------------------
    # Start background pipeline
    # --------------------------------------------

    thread = threading.Thread(
        target=run_pipeline,
        args=(
            job_id,
            repository_path,
        ),
        daemon=True,
    )

    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "repository_name": repo_name,
    }


# ============================================================
# JOB STATUS
# ============================================================

@app.get("/api/jobs/{job_id}")
def get_job(
    job_id: str,
) -> dict[str, Any]:

    job = JOBS.get(job_id)

    if not job:

        raise HTTPException(
            status_code=404,
            detail="Migration job not found.",
        )

    response = dict(job)
    response["progress"] = stage_counts(
        job.get("stage_status", {})
    )
    response["stage_titles"] = STAGE_TITLES
    return response