from __future__ import annotations

from typing import Any, Dict, List, Optional


from pipeline.embeddings.codebert_embedder import (
    CodeBERTEmbedder,
)

from pipeline.retrieval.supabase_retriever import (
    SupabaseMigrationRetriever,
)

from pipeline.retrieval.reranker import (
    MigrationReranker,
)

from pipeline.retrieval.rag_prompt import (
    build_migration_prompt,
)


class RAGMigrationService:
    """
    End-to-end migration RAG retrieval service.

    Architecture:

        source code
             ↓
        CodeBERT
             ↓
        768-d embedding
             ↓
        PRIMARY SEARCH
        exact migration pool
        Python 2 -> Python 3
             ↓
        migration-aware reranking
             ↓
        enough strong results?
             │
          YES│NO
             │
             ▼
        SECONDARY SEARCH
        generic Python -> Python
             ↓
        migration-aware reranking
             ↓
        final Top-K / NONE
             ↓
        LLM prompt

    The pipeline keeps language and version separate:

        language = Python
        source_version = 2
        target_version = 3

    The Supabase database currently stores these as:

        Python 2
        Python 3
    """

    # -----------------------------------------------------
    # Candidate retrieval
    # -----------------------------------------------------

    CANDIDATE_TOP_K = 20

    # This is deliberately lower than the final threshold.
    # It gives the reranker a useful candidate pool.
    VECTOR_THRESHOLD = 0.60

    # -----------------------------------------------------
    # Final relevance
    # -----------------------------------------------------

    FINAL_RELEVANCE_THRESHOLD = 0.78

    # -----------------------------------------------------
    # Primary-result requirement
    # -----------------------------------------------------

    MIN_PRIMARY_RESULTS = 3

    def __init__(
        self,
        top_k: int = 5,
        similarity_threshold: float = 0.78,
    ):

        self.embedder = (
            CodeBERTEmbedder()
        )

        self.retriever = (
            SupabaseMigrationRetriever()
        )

        self.reranker = (
            MigrationReranker()
        )

        self.top_k = top_k

        self.similarity_threshold = (
            similarity_threshold
        )

    # =====================================================
    # Main method
    # =====================================================

    def prepare(
        self,
        source_code: str,
        source_language: str = "Python",
        target_language: str = "Python",
        source_version: str = "2",
        target_version: str = "3",
        function_name: Optional[str] = None,
        source_lib: Optional[str] = None,
    ) -> Dict[str, Any]:

        if not source_code.strip():
            raise ValueError(
                "source_code cannot be empty."
            )

        # -------------------------------------------------
        # 1. Generate CodeBERT embedding
        # -------------------------------------------------

        embedding = self.embedder.embed(
            source_code
        )

        # -------------------------------------------------
        # 2. Convert language + version to database labels
        # -------------------------------------------------

        primary_source = (
            self._database_version_label(
                source_language,
                source_version,
            )
        )

        primary_target = (
            self._database_version_label(
                target_language,
                target_version,
            )
        )

        # Example:
        #
        # Python + 2 -> Python 2
        # Python + 3 -> Python 3

        # -------------------------------------------------
        # 3. PRIMARY RETRIEVAL
        #
        # Exact migration pool:
        #
        # Python 2 -> Python 3
        # -------------------------------------------------

        primary_candidates = (
            self.retriever.search_or_none(
                query_embedding=embedding,
                top_k=self.CANDIDATE_TOP_K,
                similarity_threshold=(
                    self.VECTOR_THRESHOLD
                ),
                source_language=primary_source,
                target_language=primary_target,
            )
            or []
        )

        # Mark candidates as primary
        for candidate in primary_candidates:

            candidate[
                "retrieval_source"
            ] = "primary"

        # -------------------------------------------------
        # 4. PRIMARY RERANKING
        # -------------------------------------------------

        primary_results = (
            self.reranker.rerank(
                candidates=primary_candidates,
                source_code=source_code,
                function_name=function_name,
                source_lib=source_lib,
                top_k=self.top_k,
                final_threshold=(
                    self.similarity_threshold
                ),
            )
        )

        # -------------------------------------------------
        # 5. SECONDARY RETRIEVAL
        #
        # Only used if primary search does not provide
        # enough strong migration examples.
        #
        # Secondary:
        #
        # Python -> Python
        # -------------------------------------------------

        secondary_candidates: List[
            Dict[str, Any]
        ] = []

        secondary_results: List[
            Dict[str, Any]
        ] = []

        if (
            len(primary_results)
            < self.MIN_PRIMARY_RESULTS
        ):

            secondary_candidates = (
                self.retriever.search_or_none(
                    query_embedding=embedding,
                    top_k=self.CANDIDATE_TOP_K,
                    similarity_threshold=(
                        self.VECTOR_THRESHOLD
                    ),
                    source_language=source_language,
                    target_language=target_language,
                )
                or []
            )

            # Mark as secondary
            for candidate in secondary_candidates:

                candidate[
                    "retrieval_source"
                ] = "secondary"

            # ---------------------------------------------
            # Secondary reranking
            # ---------------------------------------------

            secondary_results = (
                self.reranker.rerank(
                    candidates=secondary_candidates,
                    source_code=source_code,
                    function_name=function_name,
                    source_lib=source_lib,
                    top_k=self.top_k,
                    final_threshold=(
                        self.similarity_threshold
                    ),
                )
            )

            # ---------------------------------------------
            # Secondary results should not beat a primary
            # migration example merely because their raw
            # semantic score is slightly higher.
            # ---------------------------------------------

            for candidate in secondary_results:

                candidate[
                    "final_score"
                ] = round(
                    float(
                        candidate.get(
                            "final_score",
                            0.0,
                        )
                    )
                    * 0.90,
                    4,
                )

        # -------------------------------------------------
        # 6. Combine
        # -------------------------------------------------

        migrations = (
            primary_results
            + secondary_results
        )

        # -------------------------------------------------
        # 7. Final ranking
        # -------------------------------------------------

        migrations.sort(
            key=lambda item: float(
                item.get(
                    "final_score",
                    0.0,
                )
            ),
            reverse=True,
        )

        # -------------------------------------------------
        # 8. Final Top-K
        # -------------------------------------------------

        migrations = migrations[
            : self.top_k
        ]

        # -------------------------------------------------
        # 9. Build LLM prompt
        # -------------------------------------------------

        prompt = build_migration_prompt(
            source_code=source_code,
            retrieved_migrations=(
                migrations
                if migrations
                else None
            ),
            source_language=(
                f"{source_language} "
                f"{source_version}"
            ),
            target_language=(
                f"{target_language} "
                f"{target_version}"
            ),
        )

        # -------------------------------------------------
        # 10. Return result
        # -------------------------------------------------

        return {
            "source_code": source_code,

            # ---------------------------------------------
            # Embedding
            # ---------------------------------------------

            "query_embedding": embedding,

            # ---------------------------------------------
            # Migration specification
            # ---------------------------------------------

            "source_language": source_language,
            "target_language": target_language,

            "source_version": source_version,
            "target_version": target_version,

            # ---------------------------------------------
            # Database labels
            # ---------------------------------------------

            "primary_source_label": primary_source,
            "primary_target_label": primary_target,

            # ---------------------------------------------
            # RAG status
            # ---------------------------------------------

            "rag_used": bool(
                migrations
            ),

            "retrieval_count": len(
                migrations
            ),

            # ---------------------------------------------
            # Candidate statistics
            # ---------------------------------------------

            "primary_candidate_count": len(
                primary_candidates
            ),

            "primary_result_count": len(
                primary_results
            ),

            "secondary_candidate_count": len(
                secondary_candidates
            ),

            "secondary_result_count": len(
                secondary_results
            ),

            # ---------------------------------------------
            # Configuration
            # ---------------------------------------------

            "vector_threshold": (
                self.VECTOR_THRESHOLD
            ),

            "final_relevance_threshold": (
                self.similarity_threshold
            ),

            # ---------------------------------------------
            # Final results
            # ---------------------------------------------

            "retrieved_migrations": (
                migrations
            ),

            # ---------------------------------------------
            # LLM prompt
            # ---------------------------------------------

            "llm_prompt": prompt,
        }

    # =====================================================
    # Convert pipeline language/version to DB label
    # =====================================================

    @staticmethod
    def _database_version_label(
        language: str,
        version: str,
    ) -> str:

        language = (
            language or ""
        ).strip()

        version = (
            version or ""
        ).strip()

        if not version:
            return language

        # If caller already supplied "Python 2",
        # don't produce "Python 2 2".
        if language.endswith(
            f" {version}"
        ):
            return language

        return (
            f"{language} {version}"
        )