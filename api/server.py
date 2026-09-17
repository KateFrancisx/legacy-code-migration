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
    "extraction",
    "embeddings",
    "dependency",
    "planning",
    "context",
    "rag",
    "prompt",
    "llm",
]


STAGE_TITLES = {
    "scan": "Repository Scan",
    "version": "Version Detection",
    "extraction": "Code Extraction",
    "embeddings": "Semantic Embeddings",
    "dependency": "Dependency Analysis",
    "planning": "Migration Planning",
    "context": "Repository Context",
    "rag": "RAG Retrieval",
    "prompt": "Prompt Construction",
    "llm": "LLM Migration",
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
    ]

    for suffix in suffixes:

        path = output_file(
            repo_name,
            suffix,
        )

        if path.exists():
            path.unlink()

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
    # Pre-LLM stages
    # --------------------------------------------------------

    if not llm_phase:

        stage_map = {
            "1. REPOSITORY SCANNING": "scan",
            "2. PYTHON VERSION DETECTION": "version",
            "3. MIGRATION JOB SELECTION": "extraction",
            "4. CODE EXTRACTION / STATIC FEATURES": "extraction",
            "5. CODEBERT EMBEDDINGS": "embeddings",
            "6. DEPENDENCY GRAPH": "dependency",
            "7. MIGRATION PLANNING": "planning",
            "8. REPOSITORY CONTEXT": "context",
            "9. RAG MIGRATION KNOWLEDGE RETRIEVAL": "rag",
            "10. FINAL LLM PROMPTS": "prompt",
        }

        for title, stage in stage_map.items():

            if title in text:

                # Mark previous stages complete.
                stage_index = STAGES.index(
                    stage
                )

                for previous in STAGES[:stage_index]:

                    if (
                        job["stage_status"]
                        .get(previous)
                        != "failed"
                    ):
                        job["stage_status"][
                            previous
                        ] = "completed"

                update_stage(
                    job_id,
                    stage,
                    "running",
                )

                return

    # --------------------------------------------------------
    # LLM migration
    # --------------------------------------------------------

    if llm_phase:

        if text.startswith("[") and "] Migrating:" in text:

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

            # ------------------------------------------------
            # Clean stale output
            # ------------------------------------------------

            clean_previous_outputs(
                repo_name
            )

            # ------------------------------------------------
            # PRE-LLM
            # ------------------------------------------------

            env = os.environ.copy()

            # Force Python subprocesses to use UTF-8 on Windows.
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            pre_command = [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "scripts"
                    / "run_pre_llm_pipeline.py"
                ),
                str(repository_path),
            ]

            process = subprocess.Popen(
                pre_command,
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

            if return_code != 0:

                raise RuntimeError(
                    "Pre-LLM pipeline failed. "
                    "Check the pipeline log."
                )

            # Mark all pre-LLM stages completed.
            for stage in STAGES[:-1]:

                job["stage_status"][
                    stage
                ] = "completed"

            # ------------------------------------------------
            # Collect pre-LLM results
            # ------------------------------------------------

            job["results"] = collect_results(
                repo_name,
                repository_path,
            )

            job["statistics"] = (
                job["results"]
                .get(
                    "statistics",
                    {},
                )
            )

            # ------------------------------------------------
            # LLM
            # ------------------------------------------------

            update_stage(
                job_id,
                "llm",
                "running",
            )

            llm_command = [
                sys.executable,
                str(
                    PROJECT_ROOT
                    / "scripts"
                    / "run_llm_migration.py"
                ),
                str(repository_path),
            ]

            process = subprocess.Popen(
                llm_command,
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
                    llm_phase=True,
                )

            return_code = process.wait()

            if return_code != 0:

                raise RuntimeError(
                    "LLM migration failed. "
                    "Check the pipeline log."
                )

            # ------------------------------------------------
            # Final results
            # ------------------------------------------------

            job["results"] = collect_results(
                repo_name,
                repository_path,
            )

            job["statistics"] = (
                job["results"]
                .get(
                    "statistics",
                    {},
                )
            )

            job["stage_status"][
                "llm"
            ] = "completed"

            job["status"] = "completed"
            job["current_stage"] = "llm"

    except Exception as exc:

        job["status"] = "failed"
        job["error"] = str(exc)

        current = job.get(
            "current_stage"
        )

        if current in STAGES:

            job["stage_status"][
                current
            ] = "failed"


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

    return job