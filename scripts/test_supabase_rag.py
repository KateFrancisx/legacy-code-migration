from pathlib import Path
import sys


# =========================================================
# Add project root to Python path
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from pipeline.retrieval.rag_service import (
    RAGMigrationService,
)


def main():

    # =====================================================
    # Test source
    # =====================================================

    source_code = """
def process_items(items):
    for key, value in items.iteritems():
        print key, value
"""

    print(
        "=" * 70
    )

    print(
        "SUPABASE RAG RETRIEVAL TEST"
    )

    print(
        "=" * 70
    )

    # =====================================================
    # Create service
    # =====================================================

    service = RAGMigrationService(
        top_k=5,
        similarity_threshold=0.78,
    )

    # =====================================================
    # Prepare RAG
    #
    # IMPORTANT:
    #
    # language and version are separate.
    #
    # Do NOT use:
    #
    # source_language="Python 2"
    #
    # =====================================================

    result = service.prepare(
        source_code=source_code,

        source_language="Python",
        target_language="Python",

        source_version="2",
        target_version="3",

        function_name="process_items",
    )

    # =====================================================
    # Summary
    # =====================================================

    print()

    print(
        "RAG used:",
        result["rag_used"],
    )

    print(
        "Final retrieved:",
        result["retrieval_count"],
    )

    print()

    print(
        "Database migration:",
        result["primary_source_label"],
        "->",
        result["primary_target_label"],
    )

    print()

    print(
        "Vector threshold:",
        result["vector_threshold"],
    )

    print(
        "Final relevance threshold:",
        result[
            "final_relevance_threshold"
        ],
    )

    print()

    # =====================================================
    # Candidate statistics
    # =====================================================

    print(
        "PRIMARY SEARCH"
    )

    print(
        "Primary candidates:",
        result[
            "primary_candidate_count"
        ],
    )

    print(
        "Primary relevant:",
        result[
            "primary_result_count"
        ],
    )

    print()

    print(
        "SECONDARY SEARCH"
    )

    print(
        "Secondary candidates:",
        result[
            "secondary_candidate_count"
        ],
    )

    print(
        "Secondary relevant:",
        result[
            "secondary_result_count"
        ],
    )

    print()

    # =====================================================
    # Retrieved examples
    # =====================================================

    migrations = (
        result[
            "retrieved_migrations"
        ]
    )

    if not migrations:

        print(
            "=" * 70
        )

        print(
            "NO SUFFICIENTLY RELEVANT "
            "MIGRATION EXAMPLES FOUND"
        )

        print(
            "=" * 70
        )

    else:

        for index, migration in enumerate(
            migrations,
            start=1,
        ):

            print(
                "=" * 70
            )

            print(
                f"RESULT {index}"
            )

            print(
                "=" * 70
            )

            # ---------------------------------------------
            # Basic metadata
            # ---------------------------------------------

            print(
                "ID:",
                migration.get(
                    "id"
                ),
            )

            print(
                "Function:",
                migration.get(
                    "function_name"
                ),
            )

            print(
                "Retrieval source:",
                migration.get(
                    "retrieval_source"
                ),
            )

            # ---------------------------------------------
            # Scores
            # ---------------------------------------------

            print(
                "Semantic score:",
                migration.get(
                    "semantic_score"
                ),
            )

            print(
                "Migration pattern score:",
                migration.get(
                    "migration_pattern_score"
                ),
            )

            print(
                "Function score:",
                migration.get(
                    "function_score"
                ),
            )

            print(
                "Library score:",
                migration.get(
                    "library_score"
                ),
            )

            print(
                "Verified score:",
                migration.get(
                    "verified_score"
                ),
            )

            print(
                "Primary pool score:",
                migration.get(
                    "primary_pool_score"
                ),
            )

            print(
                "FINAL SCORE:",
                migration.get(
                    "final_score"
                ),
            )

            # ---------------------------------------------
            # Detected migration patterns
            # ---------------------------------------------

            print()

            print(
                "Query migration patterns:",
                migration.get(
                    "query_migration_patterns"
                ),
            )

            print(
                "Candidate migration patterns:",
                migration.get(
                    "candidate_migration_patterns"
                ),
            )

            # ---------------------------------------------
            # Original
            # ---------------------------------------------

            print()

            print(
                "Original code:"
            )

            print(
                migration.get(
                    "original_code",
                    "",
                )
            )

            # ---------------------------------------------
            # Migrated
            # ---------------------------------------------

            print()

            print(
                "Migrated code:"
            )

            print(
                migration.get(
                    "migrated_code",
                    "",
                )
            )

            print()

    # =====================================================
    # LLM prompt
    # =====================================================

    print(
        "=" * 70
    )

    print(
        "LLM PROMPT"
    )

    print(
        "=" * 70
    )

    print()

    print(
        result[
            "llm_prompt"
        ]
    )


if __name__ == "__main__":
    main()