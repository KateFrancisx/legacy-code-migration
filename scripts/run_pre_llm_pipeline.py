from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORT YOUR EXISTING COMPONENTS
# ============================================================

from pipeline.scanner.repo_scanner import scan_repository

from pipeline.version_detection.version_detector import (
    PythonVersionDetector,
    enrich_manifest,
)

from pipeline.selection.migration_job_selector import (
    select_files,
    MigrationJobSpec,
)

from pipeline.extraction.python_extractor import (
    PythonExtractor,
)

from pipeline.embeddings.codebert_embedder import (
    CodeBERTEmbedder,
)

from pipeline.retrieval.rag_service import (
    RAGMigrationService,
)

from pipeline.dependency.dependency_analyzer import (
    DependencyAnalyzer,
)

from pipeline.planning.migration_planner import (
    MigrationPlanner,
)

from pipeline.dependency.repository_context_builder import (
    RepositoryContextBuilder,
)

from pipeline.retrieval.rag_prompt import (
    build_migration_prompt,
)


# ============================================================
# HELPERS
# ============================================================

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

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


def normalize_result(result: Any) -> Any:
    """
    Convert dataclasses / pathlib objects into JSON-safe data.
    """
    if result is None:
        return None

    if hasattr(result, "to_dict"):
        return result.to_dict()

    if hasattr(result, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(result)

    if isinstance(result, Path):
        return str(result)

    if isinstance(result, dict):
        return {
            str(k): normalize_result(v)
            for k, v in result.items()
        }

    if isinstance(result, list):
        return [
            normalize_result(v)
            for v in result
        ]

    if isinstance(result, tuple):
        return [
            normalize_result(v)
            for v in result
        ]

    return result


def print_stage(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# MAIN PIPELINE
# ============================================================

def main() -> None:

    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "  python scripts\\run_pre_llm_pipeline.py <repository_path>"
        )
        sys.exit(1)

    repository_path = Path(sys.argv[1]).resolve()

    if not repository_path.exists():
        print(f"ERROR: Repository does not exist: {repository_path}")
        sys.exit(1)

    if not repository_path.is_dir():
        print(f"ERROR: Not a directory: {repository_path}")
        sys.exit(1)

    output_dir = PROJECT_ROOT / "outputs"
    output_dir.mkdir(exist_ok=True)

    repo_name = repository_path.name

    print("=" * 70)
    print("AI LEGACY CODE MIGRATION")
    print("PRE-LLM PIPELINE CHECKPOINT")
    print("=" * 70)

    print(f"Repository: {repository_path}")

    # ========================================================
    # 1. SCAN REPOSITORY
    # ========================================================

    print_stage("1. REPOSITORY SCANNING")

    scan_result = scan_repository(
        str(repository_path)
    )

    scan_result = normalize_result(scan_result)

    save_json(
        output_dir / f"{repo_name}_scan.json",
        scan_result,
    )

    if isinstance(scan_result, dict):
        files = scan_result.get("files", [])
    else:
        files = []

    print(
        f"Scanned repository successfully."
    )

    if isinstance(files, list):
        print(f"Files discovered: {len(files)}")

    # ========================================================
    # 2. PYTHON VERSION DETECTION
    # ========================================================

    print_stage("2. PYTHON VERSION DETECTION")

    detector = PythonVersionDetector()

    # IMPORTANT:
    # Preserve the scanner manifest because the migration selector
    # expects fields such as "category".
    manifest = normalize_result(scan_result)

    if not isinstance(manifest, dict):
        raise RuntimeError(
            "Scanner did not return a dictionary manifest."
        )

    # Locate the scanner's file list.
    scan_files = (
        manifest.get("files")
        or manifest.get("file_records")
        or manifest.get("python_files")
        or []
    )

    if not isinstance(scan_files, list):
        raise RuntimeError(
            "Scanner manifest does not contain a valid file list."
        )

    python_count = 0

    for entry in scan_files:

        if not isinstance(entry, dict):
            continue

        # Scanner-provided path.
        relative_path = (
            entry.get("path")
            or entry.get("relative_path")
            or entry.get("file")
        )

        if not relative_path:
            continue

        # Only analyze Python code files.
        category = entry.get("category")

        language = entry.get("language")

        is_python = (
            str(language).lower() == "python"
            or str(relative_path).lower().endswith(".py")
        )

        if category not in (None, "code") or not is_python:
            continue

        full_path = repository_path / relative_path

        if not full_path.exists():
            continue

        try:
            source = full_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            continue

        try:
            detection = detector.detect(source)
        except Exception as exc:
            detection = {
                "version": "Ambiguous",
                "confidence": 0.0,
                "error": str(exc),
            }

        detection = normalize_result(detection)

        if isinstance(detection, dict):
            entry["version_detection"] = detection
        else:
            entry["version_detection"] = {
                "version": str(detection),
                "confidence": "low",
            }

        python_count += 1

    # Enrich the EXISTING scanner manifest.
    try:
        enriched = enrich_manifest(manifest)

        if enriched is not None:
            manifest = normalize_result(enriched)

    except Exception:
        # Enrichment is optional. The detector results are still valid.
        pass

    save_json(
        output_dir / f"{repo_name}_version_manifest.json",
        manifest,
    )

    print(
        f"Python files analyzed: {python_count}"
    )

    # ========================================================
    # ========================================================
    # 3. MIGRATION JOB SELECTION
    # ========================================================

    print_stage("3. MIGRATION JOB SELECTION")

    migration_spec = MigrationJobSpec(
        language="Python",
        from_version="2",
        to_version="3",
        min_confidence="medium",
        include_ambiguous=False,
    )

    selection = select_files(
        manifest,
        migration_spec,
    )

    selection = normalize_result(selection)

    save_json(
        output_dir / f"{repo_name}_migration_selection.json",
        selection,
    )

    if not isinstance(selection, dict):
        raise RuntimeError(
            "Migration selector returned an unexpected result."
        )

    selected_files = selection.get("targets", [])

    print(
        f"Migration candidates: {len(selected_files)}"
    )

    print(
        f"Needs review: "
        f"{len(selection.get('needs_review', []))}"
    )

    print(
        f"Skipped: "
        f"{len(selection.get('skipped', []))}"
    )

    for item in selected_files:

        if isinstance(item, dict):

            file_name = (
                item.get("path")
                or item.get("file")
                or item.get("file_path")
                or "unknown"
            )

            print(
                f"  [SELECTED] {file_name}"
            )

    # ========================================================
    # 4. CODE EXTRACTION / STATIC FEATURES
    # ========================================================

    print_stage("4. CODE EXTRACTION / STATIC FEATURES")

    extractor = PythonExtractor()

    extracted = []

    for item in selected_files:

        if isinstance(item, dict):

            relative_path = (
                item.get("path")
                or item.get("file")
                or item.get("file_path")
            )

        else:
            relative_path = str(item)

        if not relative_path:
            continue

        full_path = repository_path / relative_path

        if not full_path.exists():
            print(
                f"  [SKIP] File not found: {relative_path}"
            )
            continue

        try:
            source = full_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError as exc:
            print(
                f"  [SKIP] Could not read {relative_path}: {exc}"
            )
            continue

        try:
            records = extractor.extract(
                file_path=str(relative_path),
                source=source,
                language_version="2",
            )
        except Exception as exc:
            print(
                f"  [ERROR] Extraction failed for "
                f"{relative_path}: {exc}"
            )
            continue

        records = normalize_result(records)

        if isinstance(records, list):

            for record in records:

                if isinstance(record, dict):

                    record.setdefault(
                        "file",
                        str(relative_path)
                    )

                    record.setdefault(
                        "file_path",
                        str(relative_path)
                    )

                    record.setdefault(
                        "language_version",
                        "2"
                    )

                extracted.append(record)

        print(
            f"  [EXTRACTED] {relative_path}: "
            f"{len(records) if isinstance(records, list) else 0} functions"
        )

    save_json(
        output_dir / f"{repo_name}_features.json",
        extracted,
    )

    functions = extracted

    print(
        f"Total extracted functions/features: "
        f"{len(functions)}"
    )
        
    # ========================================================
    # 5. CODEBERT EMBEDDINGS
    # ========================================================

    print_stage("5. CODEBERT EMBEDDINGS")

    embedder = CodeBERTEmbedder()

    embeddings = []

    if isinstance(functions, list):

        for item in functions:

            if not isinstance(item, dict):
                continue

            source_code = (
                item.get("source_code")
                or item.get("code")
                or item.get("original_code")
            )

            if not source_code:
                continue

            try:
                vector = embedder.embed(
                    source_code
                )
            except AttributeError:
                try:
                    vector = embedder.encode(
                        source_code
                    )
                except AttributeError:
                    vector = embedder.generate(
                        source_code
                    )

            vector = normalize_result(vector)

            record = dict(item)

            record["embedding"] = vector

            embeddings.append(record)

    save_json(
        output_dir / f"{repo_name}_embedded_features.json",
        embeddings,
    )

    print(
        f"Embeddings generated: {len(embeddings)}"
    )

    # ========================================================
    # 6. DEPENDENCY GRAPH
    # ========================================================

    print_stage("6. DEPENDENCY GRAPH")

    dependency_analyzer = DependencyAnalyzer(
        str(repository_path)
    )

    dependency_result = dependency_analyzer.analyze()

    dependency_result = normalize_result(
        dependency_result
    )

    save_json(
        output_dir / f"{repo_name}_dependency_graph.json",
        dependency_result,
    )

    if not isinstance(dependency_result, dict):
        raise RuntimeError(
            "Dependency analyzer returned an unexpected result."
        )

    # The dependency analyzer stores authoritative counts inside
    # dependency_result["statistics"].
    statistics = dependency_result.get("statistics", {})

    if not isinstance(statistics, dict):
        statistics = {}

    print(f"Python files: {statistics.get('python_files', 0)}")
    print(f"Dependency edges: {statistics.get('dependency_edges', 0)}")
    print(f"Import edges: {statistics.get('import_edges', 0)}")
    print(f"From-import edges: {statistics.get('from_import_edges', 0)}")
    print(f"Function-call edges: {statistics.get('function_call_edges', 0)}")
    print(f"Inheritance edges: {statistics.get('inheritance_edges', 0)}")

    # ========================================================
    # 7. MIGRATION PLANNING
    # ========================================================

    print_stage("7. MIGRATION PLANNING")

    planner = MigrationPlanner(
        dependency_result
    )

    migration_plan = planner.build_plan()

    migration_plan = normalize_result(
        migration_plan
    )

    save_json(
        output_dir / f"{repo_name}_migration_plan.json",
        migration_plan,
    )

    if not isinstance(migration_plan, dict):
        raise RuntimeError(
            "Migration planner returned an unexpected result."
        )

    units = (
        migration_plan.get("migration_units")
        or migration_plan.get("units")
        or []
    )

    print(
        f"Migration units: {len(units)}"
    )

    print("Migration order:")

    for index, unit in enumerate(
        units,
        start=1,
    ):

        if isinstance(unit, dict):

            file_name = (
                unit.get("file")
                or unit.get("path")
                or "unknown"
            )

            print(
                f"  {index}. {file_name}"
            )

    # ========================================================
    # 8. REPOSITORY CONTEXT
    # ========================================================

    print_stage("8. REPOSITORY CONTEXT")

    context_builder = RepositoryContextBuilder(
        repository_path=str(repository_path),
        migration_plan=migration_plan,
    )

    contexts = []

    # Build context for every migration unit.
    for unit in units:

        if not isinstance(unit, dict):
            continue

        target_file = (
            unit.get("file")
            or unit.get("path")
        )

        if not target_file:
            continue

        try:
            context = context_builder.build(
                target_file
            )
        except Exception as exc:
            context = {
                "file": target_file,
                "error": str(exc),
            }

        contexts.append(
            normalize_result(context)
        )

    save_json(
        output_dir / f"{repo_name}_migration_context.json",
        contexts,
    )

    print(
        f"Repository contexts built: {len(contexts)}"
    )

    # ========================================================
    # 9. RAG MIGRATION KNOWLEDGE RETRIEVAL
    # ========================================================

    print_stage("9. RAG MIGRATION KNOWLEDGE RETRIEVAL")

    rag_service = RAGMigrationService(
        top_k=5,
        similarity_threshold=0.78,
    )

    rag_results = []

    # --------------------------------------------------------
    # RAG is performed PER MIGRATION FUNCTION.
    #
    # IMPORTANT:
    # We pass SOURCE CODE to RAG.
    # RAG generates the CodeBERT embedding internally.
    # --------------------------------------------------------

    for function in functions:

        if not isinstance(function, dict):
            continue

        source_code = (
            function.get("source_code")
            or function.get("original_code")
            or function.get("code")
            or ""
        )

        if not source_code.strip():
            continue

        file_name = (
            function.get("file")
            or function.get("file_path")
            or function.get("path")
            or ""
        )

        function_name = (
            function.get("name")
            or function.get("function_name")
            or function.get("full_name")
        )

        # Optional library/import information.
        source_lib = None

        imports = function.get("imports")

        if isinstance(imports, list) and imports:
            source_lib = ", ".join(
                str(item)
                for item in imports
            )

        try:

            rag_result = rag_service.prepare(
                source_code=source_code,
                source_language="Python",
                target_language="Python",
                source_version="2",
                target_version="3",
                function_name=function_name,
                source_lib=source_lib,
            )

            rag_result = normalize_result(
                rag_result
            )

            rag_results.append(
                {
                    "file": file_name,
                    "function": function_name,
                    "retrieval": rag_result,
                }
            )

            retrieval_count = 0

            if isinstance(rag_result, dict):
                retrieval_count = rag_result.get(
                    "retrieval_count",
                    0,
                )

            print(
                f"  [RAG] {file_name}"
                f"{' :: ' + str(function_name) if function_name else ''}"
                f" → {retrieval_count} examples"
            )

        except Exception as exc:

            print(
                f"  [RAG ERROR] {file_name}"
                f"{' :: ' + str(function_name) if function_name else ''}"
                f" → {exc}"
            )

            rag_results.append(
                {
                    "file": file_name,
                    "function": function_name,
                    "error": str(exc),
                    "retrieval": None,
                }
            )

    save_json(
        output_dir / f"{repo_name}_rag_results.json",
        rag_results,
    )

    successful_rag = sum(
        1
        for item in rag_results
        if item.get("retrieval") is not None
    )

    print(
        f"RAG queries completed: {len(rag_results)}"
    )

    print(
        f"Successful RAG queries: {successful_rag}"
    )

    # ========================================================
    # 10. FINAL LLM PROMPTS
    # ========================================================

    print_stage("10. FINAL LLM PROMPTS")

    prompts = []

    for unit in units:

        if not isinstance(unit, dict):
            continue

        target_file = (
            unit.get("file")
            or unit.get("path")
        )

        if not target_file:
            continue

        # ----------------------------------------------------
        # Find repository context
        # ----------------------------------------------------

        context = next(
            (
                item
                for item in contexts
                if isinstance(item, dict)
                and item.get("target", {}).get("file")
                == target_file
            ),
            None,
        )

        if context is None:
            context = {}

        # ----------------------------------------------------
        # Collect RAG results belonging to this file
        # ----------------------------------------------------

        file_rag = [
            item
            for item in rag_results
            if item.get("file") == target_file
        ]

        retrieved_migrations = []

        for item in file_rag:

            retrieval = item.get(
                "retrieval"
            )

            if not isinstance(
                retrieval,
                dict,
            ):
                continue

            examples = retrieval.get(
                "retrieved_migrations",
                [],
            )

            if isinstance(examples, list):

                for example in examples:

                    example_copy = (
                        dict(example)
                        if isinstance(
                            example,
                            dict,
                        )
                        else example
                    )

                    if isinstance(
                        example_copy,
                        dict,
                    ):
                        example_copy.setdefault(
                            "query_function",
                            item.get(
                                "function"
                            ),
                        )

                    retrieved_migrations.append(
                        example_copy
                    )

        # ----------------------------------------------------
        # Target source
        # ----------------------------------------------------

        source_code = (
            context
            .get("target", {})
            .get("source_code", "")
        )

        # ----------------------------------------------------
        # Build final prompt
        # ----------------------------------------------------

        prompt = build_migration_prompt(
            source_code=source_code,
            retrieved_migrations=(
                retrieved_migrations
                if retrieved_migrations
                else None
            ),
            source_language="Python 2",
            target_language="Python 3",
            repository_context=context,
        )

        prompts.append(
            {
                "file": target_file,
                "migration_unit": unit,
                "rag_examples_count": len(
                    retrieved_migrations
                ),
                "prompt": prompt,
            }
        )

        print(
            f"  [PROMPT] {target_file}"
            f" → {len(retrieved_migrations)} RAG examples"
        )

    save_json(
        output_dir / f"{repo_name}_llm_prompts.json",
        prompts,
    )

    print(
        f"Final LLM prompts generated: "
        f"{len(prompts)}"
    )

    # ========================================================
    # FINAL CHECKPOINT
    # ========================================================

    summary = {
        "repository": str(repository_path),
        "repository_name": repo_name,

        "stages_completed": [
            "repository_scanning",
            "python_version_detection",
            "migration_job_selection",
            "code_extraction",
            "codebert_embeddings",
            "dependency_analysis",
            "migration_planning",
            "repository_context",
            "rag_retrieval",
            "llm_prompt_generation",
        ],

        "statistics": {
            "migration_units": len(units),
            "contexts": len(contexts),
            "rag_files": len(rag_results),
            "prompts": len(prompts),
            "embeddings": len(embeddings),
        },

        "llm_called": False,

        "status": "READY_FOR_LLM_MIGRATION",
    }

    save_json(
        output_dir / f"{repo_name}_pre_llm_summary.json",
        summary,
    )

    print()
    print("=" * 70)
    print("PRE-LLM PIPELINE CHECKPOINT")
    print("=" * 70)

    print()
    print("ALL PRE-LLM STAGES COMPLETED.")

    print()
    print("Completed:")
    for stage in summary["stages_completed"]:
        print(f"  [OK] {stage}")

    print()
    print("Statistics:")
    for key, value in summary["statistics"].items():
        print(f"  {key}: {value}")

    print()
    print("LLM migration: NOT RUN")
    print()
    print("System status: READY FOR LLM MIGRATION")

    print()
    print("Outputs:")
    print(
        f"  {output_dir / f'{repo_name}_scan.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_version_manifest.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_migration_selection.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_features.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_embedded_features.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_dependency_graph.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_migration_plan.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_migration_context.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_rag_results.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_llm_prompts.json'}"
    )
    print(
        f"  {output_dir / f'{repo_name}_pre_llm_summary.json'}"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()