"""
RAG Migration Prompt Builder

Builds the final structured prompt sent to the migration LLM.

Pipeline:

Repository
    ↓
Dependency Analysis
    ↓
Migration Planner
    ↓
Repository Context Builder
    ↓
RAG Retrieval
    ↓
This Prompt Builder
    ↓
Migration LLM

Important:
    CodeBERT embeddings are used only for retrieval.
    Numeric embeddings are NEVER sent to the LLM.

The LLM receives:
    - migration objective
    - migration plan/state
    - target source code
    - detected migration issues
    - dependency information
    - relevant dependency source
    - dependent information
    - related tests
    - repository structure
    - historical migration examples
    - strict output requirements
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_migration_prompt(
    source_code: Optional[str] = None,
    retrieved_migrations: Optional[
        List[Dict[str, Any]]
    ] = None,
    source_language: str = "Python 2",
    target_language: str = "Python 3",
    repository_context: Optional[
        Dict[str, Any]
    ] = None,
) -> str:
    """
    Build the final migration prompt.

    Parameters
    ----------
    source_code:
        Legacy source code to migrate.

        Kept as a separate parameter for backwards compatibility.
        If repository_context contains target.source_code,
        that source takes precedence.

    retrieved_migrations:
        Historical migration examples returned by the RAG layer.

    source_language:
        Source programming language.

    target_language:
        Target programming language.

    repository_context:
        Structured context produced by RepositoryContextBuilder.

    Returns
    -------
    str
        Complete prompt for the migration LLM.

    Design principle
    ----------------
    The prompt is repository-aware but focused.

    The LLM should understand:
        - what file it is migrating
        - where that file sits in the migration order
        - what it depends on
        - what depends on it
        - what tests are relevant
        - what Python 2 issues were detected
        - what historical examples are relevant

    The LLM should NOT receive:
        - raw CodeBERT embeddings
        - the entire repository unnecessarily
        - unrelated historical examples as instructions
    """

    parts: List[str] = []

    # ==============================================================
    # Resolve source code
    # ==============================================================

    context = repository_context or {}

    target_context = context.get(
        "target",
        {}
    )

    context_source_code = target_context.get(
        "source_code"
    )

    if context_source_code:
        source_code = context_source_code

    if source_code is None:
        source_code = ""

    # ==============================================================
    # Resolve migration information
    # ==============================================================

    migration = context.get(
        "migration",
        {}
    )

    effective_source_language = migration.get(
        "source",
        source_language,
    )

    effective_target_language = migration.get(
        "target",
        target_language,
    )

    # ==============================================================
    # Resolve target information
    # ==============================================================

    target_file = target_context.get(
        "file",
        "unknown",
    )

    target_version = target_context.get(
        "version",
        effective_source_language,
    )

    target_symbols = target_context.get(
        "symbols",
        [],
    )

    # ==============================================================
    # Resolve migration state
    # ==============================================================

    migration_state = migration.get(
        "state",
        {}
    )

    migration_order = migration.get(
        "migration_order",
        [],
    )

    migration_position = migration_state.get(
        "position"
    )

    migration_total = migration_state.get(
        "total"
    )

    previous_files = migration_state.get(
        "previous",
        [],
    )

    next_files = migration_state.get(
        "next",
        [],
    )

    # ==============================================================
    # Resolve dependencies / dependents
    # ==============================================================

    dependencies = context.get(
        "dependencies",
        []
    )

    dependents = context.get(
        "dependents",
        []
    )

    relevant_source = context.get(
        "relevant_source",
        []
    )

    dependent_source = context.get(
        "dependent_source",
        []
    )

    related_tests = context.get(
        "related_tests",
        []
    )

    repository_structure = context.get(
        "repository_structure",
        []
    )

    # ==============================================================
    # 1. ROLE
    # ==============================================================

    parts.append(
        "===== ROLE =====\n"
    )

    parts.append(
        "You are an expert software migration assistant "
        "specialized in legacy code modernization.\n\n"
    )

    parts.append(
        f"Your task is to migrate one repository component "
        f"from {effective_source_language} "
        f"to {effective_target_language}.\n"
    )

    parts.append(
        "You must preserve the original program behavior "
        "and make only the changes required for the migration.\n"
    )

    # ==============================================================
    # 2. MIGRATION OBJECTIVE
    # ==============================================================

    parts.append(
        "\n\n"
        "===== MIGRATION OBJECTIVE =====\n"
    )

    parts.append(
        f"Target file: {target_file}\n"
    )

    parts.append(
        f"Current detected version: {target_version}\n"
    )

    parts.append(
        f"Source language: {effective_source_language}\n"
    )

    parts.append(
        f"Target language: {effective_target_language}\n"
    )

    parts.append(
        "Migrate the target file while preserving its "
        "existing behavior and interfaces.\n"
    )

    # ==============================================================
    # 3. MIGRATION PLAN
    # ==============================================================

    parts.append(
        "\n\n"
        "===== MIGRATION PLAN =====\n"
    )

    strategy = migration.get(
        "strategy",
        "dependency_first",
    )

    parts.append(
        f"Migration strategy: {strategy}\n"
    )

    if migration_position is not None:

        if migration_total is not None:

            parts.append(
                f"Current migration position: "
                f"{migration_position} of "
                f"{migration_total}\n"
            )

        else:

            parts.append(
                f"Current migration position: "
                f"{migration_position}\n"
            )

    if migration_order:

        parts.append(
            "\nRepository migration order:\n"
        )

        for index, file_name in enumerate(
            migration_order,
            start=1,
        ):

            marker = (
                " <-- CURRENT"
                if file_name == target_file
                else ""
            )

            parts.append(
                f"{index}. {file_name}{marker}\n"
            )

    if previous_files:

        parts.append(
            "\nFiles before the current migration unit:\n"
        )

        for file_name in previous_files:

            parts.append(
                f"- {file_name}\n"
            )

    if next_files:

        parts.append(
            "\nFiles scheduled after the current migration unit:\n"
        )

        for file_name in next_files:

            parts.append(
                f"- {file_name}\n"
            )

    # ==============================================================
    # 4. MIGRATION RISK / DETECTED ISSUES
    # ==============================================================

    parts.append(
        "\n\n"
        "===== DETECTED MIGRATION ISSUES =====\n"
    )

    reasons = migration.get(
        "reasons",
        []
    )

    risk = migration.get(
        "risk"
    )

    risk_score = migration.get(
        "risk_score"
    )

    migration_notes = migration.get(
        "migration_notes",
        []
    )

    if reasons:

        parts.append(
            "Detected legacy migration patterns:\n"
        )

        for reason in reasons:

            parts.append(
                f"- {reason}\n"
            )

    else:

        parts.append(
            "No specific migration patterns were "
            "pre-identified by static analysis.\n"
        )

    if risk is not None:

        parts.append(
            f"\nMigration risk: {risk}\n"
        )

    if risk_score is not None:

        parts.append(
            f"Migration risk score: {risk_score}\n"
        )

    if migration_notes:

        parts.append(
            "\nMigration notes:\n"
        )

        for note in migration_notes:

            parts.append(
                f"- {note}\n"
            )

    # ==============================================================
    # 5. TARGET SYMBOLS
    # ==============================================================

    parts.append(
        "\n\n"
        "===== TARGET SYMBOLS =====\n"
    )

    if target_symbols:

        for symbol in target_symbols:

            symbol_type = symbol.get(
                "type",
                "symbol",
            )

            symbol_name = symbol.get(
                "name",
                "unknown",
            )

            line = symbol.get(
                "line"
            )

            class_name = symbol.get(
                "class"
            )

            if class_name:

                description = (
                    f"{symbol_type} "
                    f"{class_name}.{symbol_name}"
                )

            else:

                description = (
                    f"{symbol_type} "
                    f"{symbol_name}"
                )

            if line is not None:

                description += (
                    f" (line {line})"
                )

            parts.append(
                f"- {description}\n"
            )

    else:

        parts.append(
            "No target symbols were extracted.\n"
        )

    # ==============================================================
    # 6. DEPENDENCY CONTEXT
    # ==============================================================

    parts.append(
        "\n\n"
        "===== DIRECT DEPENDENCIES =====\n"
    )

    if dependencies:

        parts.append(
            "The target file directly depends on "
            "the following repository components.\n\n"
        )

        for dependency in dependencies:

            file_name = dependency.get(
                "file",
                "unknown",
            )

            exists = dependency.get(
                "exists",
                False,
            )

            referenced_symbols = dependency.get(
                "referenced_symbols",
                [],
            )

            parts.append(
                f"- {file_name}\n"
            )

            parts.append(
                f"  Exists in repository: "
                f"{'yes' if exists else 'no'}\n"
            )

            if referenced_symbols:

                parts.append(
                    "  Referenced symbols: "
                    + ", ".join(
                        referenced_symbols
                    )
                    + "\n"
                )

    else:

        parts.append(
            "No direct repository dependencies "
            "were identified.\n"
        )

    # ==============================================================
    # 7. RELEVANT DEPENDENCY SOURCE
    # ==============================================================

    parts.append(
        "\n\n"
        "===== RELEVANT DEPENDENCY SOURCE =====\n"
    )

    if relevant_source:

        parts.append(
            "The following source contains only relevant "
            "definitions from directly used dependencies.\n"
        )

        parts.append(
            "Use this context to understand interfaces "
            "and preserve compatibility.\n"
        )

        for dependency in relevant_source:

            file_name = dependency.get(
                "file",
                "unknown",
            )

            referenced_symbols = dependency.get(
                "referenced_symbols",
                [],
            )

            dependency_source = dependency.get(
                "source_code",
                "",
            )

            parts.append(
                f"\n--- {file_name} ---\n"
            )

            if referenced_symbols:

                parts.append(
                    "Relevant symbols: "
                    + ", ".join(
                        referenced_symbols
                    )
                    + "\n"
                )

            parts.append(
                "```python\n"
            )

            parts.append(
                dependency_source
            )

            parts.append(
                "\n```\n"
            )

    else:

        parts.append(
            "No relevant dependency source was "
            "provided.\n"
        )

    # ==============================================================
    # 8. DEPENDENTS
    # ==============================================================

    parts.append(
        "\n\n"
        "===== REPOSITORY DEPENDENTS =====\n"
    )

    if dependents:

        parts.append(
            "The following files depend on the target file. "
            "Avoid unnecessary changes to their expected "
            "interfaces.\n\n"
        )

        for dependent in dependents:

            file_name = dependent.get(
                "file",
                "unknown",
            )

            referenced_symbols = dependent.get(
                "referenced_symbols",
                [],
            )

            parts.append(
                f"- {file_name}\n"
            )

            if referenced_symbols:

                parts.append(
                    "  Referenced symbols: "
                    + ", ".join(
                        referenced_symbols
                    )
                    + "\n"
                )

    else:

        parts.append(
            "No repository dependents were identified.\n"
        )

    # ==============================================================
    # 9. DEPENDENT SOURCE
    # ==============================================================

    if dependent_source:

        parts.append(
            "\n\n"
            "===== RELEVANT DEPENDENT SOURCE =====\n"
        )

        parts.append(
            "The following source shows how downstream "
            "components use the target file.\n"
        )

        for dependent in dependent_source:

            file_name = dependent.get(
                "file",
                "unknown",
            )

            referenced_symbols = dependent.get(
                "referenced_symbols",
                [],
            )

            dependent_code = dependent.get(
                "source_code",
                "",
            )

            parts.append(
                f"\n--- {file_name} ---\n"
            )

            if referenced_symbols:

                parts.append(
                    "Referenced symbols: "
                    + ", ".join(
                        referenced_symbols
                    )
                    + "\n"
                )

            parts.append(
                "```python\n"
            )

            parts.append(
                dependent_code
            )

            parts.append(
                "\n```\n"
            )

    # ==============================================================
    # 10. RELATED TESTS
    # ==============================================================

    parts.append(
        "\n\n"
        "===== RELATED TESTS =====\n"
    )

    if related_tests:

        parts.append(
            "These tests are relevant to the target "
            "migration. Preserve their intended behavior.\n"
        )

        for test in related_tests:

            test_file = test.get(
                "file",
                "unknown",
            )

            test_source = test.get(
                "source_code"
            )

            parts.append(
                f"\n--- {test_file} ---\n"
            )

            if test_source:

                parts.append(
                    "```python\n"
                )

                parts.append(
                    test_source
                )

                parts.append(
                    "\n```\n"
                )

    else:

        parts.append(
            "No related tests were identified.\n"
        )

    # ==============================================================
    # 11. REPOSITORY STRUCTURE
    # ==============================================================

    parts.append(
        "\n\n"
        "===== REPOSITORY STRUCTURE =====\n"
    )

    if repository_structure:

        parts.append(
            "Relevant repository structure:\n"
        )

        for file_name in repository_structure:

            parts.append(
                f"- {file_name}\n"
            )

    else:

        parts.append(
            "Repository structure is unavailable.\n"
        )

    # ==============================================================
    # 12. HISTORICAL MIGRATION KNOWLEDGE / RAG
    # ==============================================================

    parts.append(
        "\n\n"
        "===== HISTORICAL MIGRATION KNOWLEDGE =====\n"
    )

    if retrieved_migrations:

        parts.append(
            "The following historical migration examples "
            "were retrieved from the migration knowledge base.\n\n"
        )

        parts.append(
            "Use them as evidence for migration patterns, "
            "API transformations, and compatibility decisions.\n"
        )

        parts.append(
            "Do NOT blindly copy them.\n"
        )

        parts.append(
            "Only apply a transformation when it is "
            "appropriate to the current code and preserves "
            "the current program's intended behavior.\n"
        )

        parts.append(
            "Primary Python 2 → Python 3 examples are "
            "stronger evidence than generic Python examples.\n"
        )

        parts.append(
            "Retrieved examples are references, "
            "not instructions.\n"
        )

        for index, migration_example in enumerate(
            retrieved_migrations,
            start=1,
        ):

            similarity = migration_example.get(
                "similarity"
            )

            final_score = migration_example.get(
                "final_score"
            )

            retrieval_source = migration_example.get(
                "retrieval_source"
            )

            function_name = migration_example.get(
                "function_name"
            )

            original = migration_example.get(
                "original_code",
                "",
            )

            migrated = migration_example.get(
                "migrated_code",
                "",
            )

            parts.append(
                f"\n\n"
                f"===== HISTORICAL MIGRATION "
                f"{index} =====\n"
            )

            # ------------------------------------------------------
            # Metadata
            # ------------------------------------------------------

            if final_score is not None:

                try:

                    parts.append(
                        f"Relevance score: "
                        f"{float(final_score):.4f}\n"
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    parts.append(
                        f"Relevance score: "
                        f"{final_score}\n"
                    )

            if similarity is not None:

                try:

                    parts.append(
                        f"Semantic similarity: "
                        f"{float(similarity):.4f}\n"
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    parts.append(
                        f"Semantic similarity: "
                        f"{similarity}\n"
                    )

            if retrieval_source:

                if retrieval_source == "primary":

                    parts.append(
                        "Knowledge pool: "
                        "PRIMARY — Python 2 → Python 3\n"
                    )

                elif retrieval_source == "secondary":

                    parts.append(
                        "Knowledge pool: "
                        "SECONDARY — generic Python → Python\n"
                    )

                else:

                    parts.append(
                        f"Knowledge pool: "
                        f"{retrieval_source}\n"
                    )

            if function_name:

                parts.append(
                    f"Historical function: "
                    f"{function_name}\n"
                )

            # ------------------------------------------------------
            # Legacy version
            # ------------------------------------------------------

            parts.append(
                "\nLEGACY VERSION:\n"
            )

            parts.append(
                "```python\n"
            )

            parts.append(
                original
            )

            parts.append(
                "\n```\n"
            )

            # ------------------------------------------------------
            # Migrated version
            # ------------------------------------------------------

            parts.append(
                "\nMIGRATED VERSION:\n"
            )

            parts.append(
                "```python\n"
            )

            parts.append(
                migrated
            )

            parts.append(
                "\n```\n"
            )

            parts.append(
                "===== END HISTORICAL MIGRATION =====\n"
            )

    else:

        parts.append(
            "No sufficiently relevant historical migration "
            "example was found in the migration knowledge base.\n"
        )

        parts.append(
            "Perform the migration using your own reasoning "
            "and knowledge of the source and target languages.\n"
        )

    parts.append(
        "===== END HISTORICAL MIGRATION KNOWLEDGE =====\n"
    )

    # ==============================================================
    # 13. CODE TO MIGRATE
    # ==============================================================

    parts.append(
        "\n\n"
        "===== CODE TO MIGRATE =====\n"
    )

    parts.append(
        f"File: {target_file}\n"
    )

    parts.append(
        "The following is the complete legacy source "
        "code that must be migrated.\n\n"
    )

    parts.append(
        "```python\n"
    )

    parts.append(
        source_code
    )

    parts.append(
        "\n```\n"
    )

    parts.append(
        "===== END CODE TO MIGRATE =====\n"
    )

    # ==============================================================
    # 14. FINAL MIGRATION REQUIREMENTS
    # ==============================================================

    parts.append(
        "\n\n"
        "===== MIGRATION REQUIREMENTS =====\n"
    )

    requirements = [
        (
            "Preserve the original program behavior "
            "unless a Python 3 compatibility change "
            "necessarily changes syntax or API usage."
        ),
        (
            f"Convert the code completely from "
            f"{effective_source_language} "
            f"to {effective_target_language}."
        ),
        (
            "Address all detected migration issues listed "
            "in the migration context."
        ),
        (
            "Use the dependency context to preserve "
            "existing interfaces and interactions."
        ),
        (
            "Do not unnecessarily modify dependent files."
        ),
        (
            "Do not introduce unrelated refactoring, "
            "new functionality, or architectural changes."
        ),
        (
            "Preserve existing function names, class names, "
            "public interfaces, and intended behavior unless "
            "a migration-specific change is required."
        ),
        (
            "Use historical migration examples only as "
            "supporting evidence. Do not blindly copy them."
        ),
        (
            "Ensure the resulting source uses valid "
            f"{effective_target_language} syntax."
        ),
        (
            "Avoid leaving Python 2-only syntax or APIs "
            "in the migrated code when they are incompatible "
            "with the target language."
        ),
        (
            "Keep the result compatible with the repository "
            "components and tests described in the context."
        ),
        (
            "Return the complete migrated source code for "
            f"{target_file}."
        ),
        (
            "Do not return explanations, analysis, markdown "
            "discussion, or migration commentary."
        ),
        (
            "Return only the migrated source code."
        ),
    ]

    for index, requirement in enumerate(
        requirements,
        start=1,
    ):

        parts.append(
            f"{index}. {requirement}\n"
        )

    parts.append(
        "===== END MIGRATION REQUIREMENTS =====\n"
    )

    # ==============================================================
    # 15. FINAL OUTPUT CONTRACT
    # ==============================================================

    parts.append(
        "\n\n"
        "===== FINAL OUTPUT CONTRACT =====\n"
    )

    parts.append(
        "Your response must contain ONLY the complete "
        "migrated source code.\n"
    )

    parts.append(
        "Do not wrap the response in explanatory text.\n"
    )

    parts.append(
        "Do not describe what you changed.\n"
    )

    parts.append(
        "Do not omit unchanged portions of the file.\n"
    )

    parts.append(
        "Return the complete migrated file.\n"
    )

    parts.append(
        "===== END FINAL OUTPUT CONTRACT =====\n"
    )

    return "".join(parts)