from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


class SupabaseMigrationRetriever:
    """
    Retrieves migration examples from Supabase using
    pgvector cosine similarity.

    The database contains two useful pools:

    PRIMARY:
        Python 2 -> Python 3

    SECONDARY:
        Python -> Python

    This class performs the vector search only.
    Metadata-aware reranking is handled separately
    by MigrationReranker.
    """

    RPC_FUNCTION = "search_migration_examples"

    EMBEDDING_DIMENSION = 768

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):

        self.supabase_url = (
            supabase_url
            or os.getenv("SUPABASE_URL")
        )

        self.supabase_key = (
            supabase_key
            or os.getenv("SUPABASE_KEY")
        )

        if not self.supabase_url:
            raise ValueError(
                "SUPABASE_URL is not configured."
            )

        if not self.supabase_key:
            raise ValueError(
                "SUPABASE_KEY is not configured."
            )

        self.client: Client = create_client(
            self.supabase_url,
            self.supabase_key,
        )

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        similarity_threshold: float = 0.60,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.

        This retrieves a candidate pool. It does NOT decide
        whether the candidates are actually useful.

        Final relevance is determined by MigrationReranker.
        """

        # -------------------------------------------------
        # Validate embedding
        # -------------------------------------------------

        if not query_embedding:
            raise ValueError(
                "Query embedding is empty."
            )

        if len(query_embedding) != self.EMBEDDING_DIMENSION:
            raise ValueError(
                f"Expected a "
                f"{self.EMBEDDING_DIMENSION}-dimensional "
                f"embedding, "
                f"got {len(query_embedding)}."
            )

        # -------------------------------------------------
        # Validate parameters
        # -------------------------------------------------

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError(
                "similarity_threshold must be "
                "between 0 and 1."
            )

        # -------------------------------------------------
        # Supabase RPC
        # -------------------------------------------------

        response = self.client.rpc(
            self.RPC_FUNCTION,
            {
                "query_embedding": query_embedding,
                "match_threshold": similarity_threshold,
                "match_count": top_k,
                "filter_source_language": source_language,
                "filter_target_language": target_language,
            },
        ).execute()

        return response.data or []

    def search_or_none(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        similarity_threshold: float = 0.60,
        source_language: Optional[str] = None,
        target_language: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:

        results = self.search(
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            source_language=source_language,
            target_language=target_language,
        )

        return results if results else None