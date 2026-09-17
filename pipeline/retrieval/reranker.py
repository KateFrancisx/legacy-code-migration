from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


class MigrationReranker:
    """
    Reranks Supabase CodeBERT candidates for code migration.

    Strategy:

        CodeBERT semantic similarity
                    +
        migration-pattern evidence
                    +
        function-name evidence
                    +
        import/library evidence
                    +
        verification evidence

    Important:
        The fact that a candidate belongs to the primary
        Python 2 -> Python 3 pool is NOT given a score boost.

        The database filter already handles that.

        Instead, candidates are rewarded when their actual
        migration transformation is relevant to the query.
    """

    # =====================================================
    # SCORE CONFIGURATION
    # =====================================================

    # Migration transformation is the most important
    # additional signal after CodeBERT similarity.
    MIGRATION_PATTERN_BOOST = 0.15

    FUNCTION_MATCH_BOOST = 0.05

    LIBRARY_MATCH_BOOST = 0.05

    VERIFIED_BOOST = 0.03

    # Minimum semantic similarity required before a
    # candidate is considered by the reranker.
    MIN_SEMANTIC_SIMILARITY = 0.70

    # Minimum final relevance required to send a candidate
    # to the LLM.
    FINAL_THRESHOLD = 0.78

    # =====================================================
    # PUBLIC API
    # =====================================================

    def rerank(
        self,
        candidates: List[Dict[str, Any]],
        source_code: str,
        function_name: Optional[str] = None,
        source_lib: Optional[str] = None,
        top_k: int = 5,
        final_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rerank vector-search candidates.

        Returns:
            Top-K relevant candidates.

        Returns [] if no candidate reaches the
        final relevance threshold.
        """

        if not candidates:
            return []

        threshold = (
            final_threshold
            if final_threshold is not None
            else self.FINAL_THRESHOLD
        )

        # -------------------------------------------------
        # Analyze query
        # -------------------------------------------------

        query_patterns = (
            self._extract_migration_patterns(
                source_code
            )
        )

        query_imports = (
            self._extract_imports(
                source_code
            )
        )

        scored: List[Dict[str, Any]] = []

        # -------------------------------------------------
        # Score candidates
        # -------------------------------------------------

        for candidate in candidates:

            semantic_score = (
                self._semantic_score(
                    candidate
                )
            )

            # ---------------------------------------------
            # Ignore obviously weak vector matches
            # ---------------------------------------------

            if (
                semantic_score
                < self.MIN_SEMANTIC_SIMILARITY
            ):
                continue

            # ---------------------------------------------
            # Migration-pattern relevance
            # ---------------------------------------------

            migration_pattern_score = (
                self._migration_pattern_score(
                    candidate,
                    query_patterns,
                )
            )

            # ---------------------------------------------
            # Function-name relevance
            # ---------------------------------------------

            function_score = (
                self._function_score(
                    candidate,
                    function_name,
                )
            )

            # ---------------------------------------------
            # Library/import relevance
            # ---------------------------------------------

            library_score = (
                self._library_score(
                    candidate,
                    source_lib,
                    query_imports,
                )
            )

            # ---------------------------------------------
            # Verification
            # ---------------------------------------------

            verified_score = (
                1.0
                if candidate.get(
                    "verified"
                ) is True
                else 0.0
            )

            # =================================================
            # FINAL SCORE
            # =================================================
            #
            # Semantic similarity is the BASE.
            #
            # Everything else is an evidence BOOST.
            #
            # There is intentionally NO primary-pool boost.
            #
            # Python 2 -> Python 3 filtering already happens
            # in Supabase.
            # =================================================

            final_score = semantic_score

            # Strongest contextual signal:
            # actual migration transformation match.
            if migration_pattern_score > 0:

                final_score += (
                    self.MIGRATION_PATTERN_BOOST
                    * migration_pattern_score
                )

            # Function-name match.
            if function_score > 0:

                final_score += (
                    self.FUNCTION_MATCH_BOOST
                    * function_score
                )

            # Library/import match.
            if library_score > 0:

                final_score += (
                    self.LIBRARY_MATCH_BOOST
                    * library_score
                )

            # Verified historical migration.
            if verified_score > 0:

                final_score += (
                    self.VERIFIED_BOOST
                )

            # Cap at 1.0.
            final_score = min(
                final_score,
                1.0,
            )

            # -------------------------------------------------
            # Copy candidate so we don't mutate the original
            # -------------------------------------------------

            enriched = dict(candidate)

            enriched[
                "semantic_score"
            ] = round(
                semantic_score,
                4,
            )

            enriched[
                "migration_pattern_score"
            ] = round(
                migration_pattern_score,
                4,
            )

            enriched[
                "function_score"
            ] = round(
                function_score,
                4,
            )

            enriched[
                "library_score"
            ] = round(
                library_score,
                4,
            )

            enriched[
                "verified_score"
            ] = round(
                verified_score,
                4,
            )

            enriched[
                "final_score"
            ] = round(
                final_score,
                4,
            )

            # -------------------------------------------------
            # Debug information
            # -------------------------------------------------

            enriched[
                "query_migration_patterns"
            ] = sorted(
                query_patterns
            )

            enriched[
                "candidate_migration_patterns"
            ] = sorted(
                self._candidate_pair_patterns(
                    candidate
                )
            )

            scored.append(
                enriched
            )

        # =====================================================
        # SORT
        # =====================================================

        scored.sort(
            key=lambda item: float(
                item.get(
                    "final_score",
                    0.0,
                )
            ),
            reverse=True,
        )

        # =====================================================
        # FINAL THRESHOLD
        # =====================================================

        relevant = [
            item
            for item in scored
            if float(
                item.get(
                    "final_score",
                    0.0,
                )
            ) >= threshold
        ]

        return relevant[:top_k]

    # =====================================================
    # SEMANTIC SCORE
    # =====================================================

    @staticmethod
    def _semantic_score(
        candidate: Dict[str, Any],
    ) -> float:

        value = candidate.get(
            "similarity",
            0.0,
        )

        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    # =====================================================
    # QUERY MIGRATION PATTERNS
    # =====================================================

    @staticmethod
    def _extract_migration_patterns(
        source_code: str,
    ) -> Set[str]:
        """
        Detect known Python 2 migration indicators
        in the user's source code.
        """

        code = source_code or ""

        patterns: Set[str] = set()

        known_patterns = {

            "iteritems":
                r"\.iteritems\s*\(",

            "iterkeys":
                r"\.iterkeys\s*\(",

            "itervalues":
                r"\.itervalues\s*\(",

            "xrange":
                r"\bxrange\s*\(",

            "raw_input":
                r"\braw_input\s*\(",

            "has_key":
                r"\.has_key\s*\(",

            "urllib2":
                r"\burllib2\b",

            "cStringIO":
                r"\bcStringIO\b",

            "basestring":
                r"\bbasestring\b",

            "unicode":
                r"\bunicode\b",

            "long":
                r"\blong\b",

            "print_statement":
                r"(?m)^\s*print\s+[^(\n]",

            "assertEquals":
                r"\.assertEquals\s*\(",

            "assertNotEquals":
                r"\.assertNotEquals\s*\(",

            "exec_statement":
                r"(?m)^\s*exec\s+",
        }

        for (
            name,
            pattern,
        ) in known_patterns.items():

            if re.search(
                pattern,
                code,
            ):

                patterns.add(
                    name
                )

        return patterns

    # =====================================================
    # HISTORICAL PAIR PATTERNS
    # =====================================================

    @classmethod
    def _candidate_pair_patterns(
        cls,
        candidate: Dict[str, Any],
    ) -> Set[str]:
        """
        Detect which Python 2 -> Python 3
        transformation(s) occurred in a historical pair.
        """

        original = (
            candidate.get(
                "original_code",
                "",
            )
            or ""
        )

        migrated = (
            candidate.get(
                "migrated_code",
                "",
            )
            or ""
        )

        return cls._extract_pair_patterns(
            original,
            migrated,
        )

    @staticmethod
    def _extract_pair_patterns(
        original: str,
        migrated: str,
    ) -> Set[str]:
        """
        Detect known transformations by comparing
        original_code and migrated_code.
        """

        patterns: Set[str] = set()

        # -------------------------------------------------
        # iteritems -> items
        # -------------------------------------------------

        if (
            re.search(
                r"\.iteritems\s*\(",
                original,
            )
            and re.search(
                r"\.items\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "iteritems"
            )

        # -------------------------------------------------
        # iterkeys -> keys
        # -------------------------------------------------

        if (
            re.search(
                r"\.iterkeys\s*\(",
                original,
            )
            and re.search(
                r"\.keys\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "iterkeys"
            )

        # -------------------------------------------------
        # itervalues -> values
        # -------------------------------------------------

        if (
            re.search(
                r"\.itervalues\s*\(",
                original,
            )
            and re.search(
                r"\.values\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "itervalues"
            )

        # -------------------------------------------------
        # xrange -> range
        # -------------------------------------------------

        if (
            re.search(
                r"\bxrange\s*\(",
                original,
            )
            and re.search(
                r"\brange\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "xrange"
            )

        # -------------------------------------------------
        # raw_input -> input
        # -------------------------------------------------

        if (
            re.search(
                r"\braw_input\s*\(",
                original,
            )
            and re.search(
                r"\binput\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "raw_input"
            )

        # -------------------------------------------------
        # has_key -> "in"
        # -------------------------------------------------

        if (
            re.search(
                r"\.has_key\s*\(",
                original,
            )
            and re.search(
                r"\bin\b",
                migrated,
            )
        ):

            patterns.add(
                "has_key"
            )

        # -------------------------------------------------
        # basestring -> str / six.string_types
        # -------------------------------------------------

        if (
            re.search(
                r"\bbasestring\b",
                original,
            )
            and (
                re.search(
                    r"\bstr\b",
                    migrated,
                )
                or re.search(
                    r"\bsix\.string_types\b",
                    migrated,
                )
            )
        ):

            patterns.add(
                "basestring"
            )

        # -------------------------------------------------
        # unicode -> str
        # -------------------------------------------------

        if (
            re.search(
                r"\bunicode\b",
                original,
            )
            and re.search(
                r"\bstr\b",
                migrated,
            )
        ):

            patterns.add(
                "unicode"
            )

        # -------------------------------------------------
        # long -> int
        # -------------------------------------------------

        if (
            re.search(
                r"\blong\b",
                original,
            )
            and re.search(
                r"\bint\b",
                migrated,
            )
        ):

            patterns.add(
                "long"
            )

        # -------------------------------------------------
        # Python 2 print statement -> print()
        # -------------------------------------------------

        if (
            re.search(
                r"(?m)^\s*print\s+[^(\n]",
                original,
            )
            and re.search(
                r"(?m)^\s*print\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "print_statement"
            )

        # -------------------------------------------------
        # assertEquals -> assertEqual
        # -------------------------------------------------

        if (
            re.search(
                r"\.assertEquals\s*\(",
                original,
            )
            and re.search(
                r"\.assertEqual\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "assertEquals"
            )

        # -------------------------------------------------
        # assertNotEquals -> assertNotEqual
        # -------------------------------------------------

        if (
            re.search(
                r"\.assertNotEquals\s*\(",
                original,
            )
            and re.search(
                r"\.assertNotEqual\s*\(",
                migrated,
            )
        ):

            patterns.add(
                "assertNotEquals"
            )

        # -------------------------------------------------
        # urllib2 -> urllib.request
        # -------------------------------------------------

        if (
            re.search(
                r"\burllib2\b",
                original,
            )
            and re.search(
                r"\burllib\.request\b",
                migrated,
            )
        ):

            patterns.add(
                "urllib2"
            )

        return patterns

    # =====================================================
    # MIGRATION PATTERN SCORE
    # =====================================================

    def _migration_pattern_score(
        self,
        candidate: Dict[str, Any],
        query_patterns: Set[str],
    ) -> float:
        """
        Compare migration patterns in the query against
        migration transformations in the historical pair.

        Example:

            Query:
                iteritems
                print_statement

            Historical pair:
                iteritems

        Score:

            1 / 2 = 0.5

        If both match:

            2 / 2 = 1.0
        """

        if not query_patterns:
            return 0.0

        candidate_patterns = (
            self._candidate_pair_patterns(
                candidate
            )
        )

        if not candidate_patterns:
            return 0.0

        overlap = (
            query_patterns
            & candidate_patterns
        )

        if not overlap:
            return 0.0

        return min(
            len(overlap)
            / len(query_patterns),
            1.0,
        )

    # =====================================================
    # FUNCTION SCORE
    # =====================================================

    @staticmethod
    def _function_score(
        candidate: Dict[str, Any],
        query_function_name: Optional[str],
    ) -> float:

        if not query_function_name:
            return 0.0

        candidate_name = (
            candidate.get(
                "function_name",
                "",
            )
            or ""
        )

        if not candidate_name:
            return 0.0

        query_name = (
            query_function_name
            .strip()
            .lower()
        )

        candidate_name = (
            candidate_name
            .strip()
            .lower()
        )

        # Exact function match.
        if (
            query_name
            == candidate_name
        ):

            return 1.0

        # Partial name match.
        if (
            query_name in candidate_name
            or candidate_name in query_name
        ):

            return 0.5

        return 0.0

    # =====================================================
    # LIBRARY / IMPORT SCORE
    # =====================================================

    @staticmethod
    def _library_score(
        candidate: Dict[str, Any],
        source_lib: Optional[str],
        query_imports: Set[str],
    ) -> float:

        score = 0.0

        candidate_lib = (
            candidate.get(
                "source_lib",
                "",
            )
            or ""
        ).strip().lower()

        # -------------------------------------------------
        # Explicit source library
        # -------------------------------------------------

        if (
            source_lib
            and candidate_lib
            and source_lib.strip().lower()
            == candidate_lib
        ):

            score = max(
                score,
                1.0,
            )

        # -------------------------------------------------
        # Import overlap
        # -------------------------------------------------

        candidate_imports = (
            MigrationReranker
            ._candidate_imports(
                candidate
            )
        )

        if (
            query_imports
            and candidate_imports
        ):

            overlap = (
                query_imports
                & candidate_imports
            )

            if overlap:

                score = max(
                    score,
                    min(
                        len(overlap)
                        / len(query_imports),
                        1.0,
                    ),
                )

        return score

    # =====================================================
    # QUERY IMPORT EXTRACTION
    # =====================================================

    @staticmethod
    def _extract_imports(
        source_code: str,
    ) -> Set[str]:

        imports: Set[str] = set()

        code = source_code or ""

        for match in re.finditer(
            r"^\s*"
            r"(?:import|from)"
            r"\s+"
            r"([A-Za-z_][\w.]*)",
            code,
            re.MULTILINE,
        ):

            imports.add(
                match.group(1)
                .lower()
            )

        return imports

    # =====================================================
    # CANDIDATE IMPORT EXTRACTION
    # =====================================================

    @staticmethod
    def _candidate_imports(
        candidate: Dict[str, Any],
    ) -> Set[str]:

        imports: Set[str] = set()

        # -------------------------------------------------
        # source_lib
        # -------------------------------------------------

        candidate_lib = (
            candidate.get(
                "source_lib",
                "",
            )
            or ""
        )

        if candidate_lib:

            for item in candidate_lib.split(","):

                item = (
                    item.strip()
                    .lower()
                )

                if item:

                    imports.add(
                        item
                    )

        # -------------------------------------------------
        # imports_original
        # -------------------------------------------------

        raw_imports = candidate.get(
            "imports_original"
        )

        if isinstance(
            raw_imports,
            list,
        ):

            for item in raw_imports:

                if isinstance(
                    item,
                    str,
                ):

                    imports.add(
                        item.lower()
                    )

                elif isinstance(
                    item,
                    dict,
                ):

                    for value in (
                        item.values()
                    ):

                        if isinstance(
                            value,
                            str,
                        ):

                            imports.add(
                                value.lower()
                            )

        return imports