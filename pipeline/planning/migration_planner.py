from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set


class MigrationPlanner:
    """
    Repository-level Python 2 -> Python 3 migration planner.

    Dependency direction:

        A -> B

    means A depends on B.

    Therefore:

        B should normally migrate before A.

    The planner:

        1. identifies Python 2 production files
        2. separates tests
        3. calculates dependency relationships
        4. calculates reverse dependents
        5. estimates migration risk
        6. identifies Python 2 migration reasons
        7. produces dependency-first migration order
        8. identifies affected tests
        9. detects dependency cycles
    """

    def __init__(
        self,
        dependency_result: Dict[str, Any],
    ):

        self.result = dependency_result

        self.files = (
            dependency_result.get(
                "files",
                []
            )
        )

        self.metadata = (
            dependency_result.get(
                "file_metadata",
                {}
            )
        )

        self.graph = (
            dependency_result.get(
                "graph",
                {}
            )
        )

        self.reverse_graph = (
            dependency_result.get(
                "reverse_graph",
                {}
            )
        )

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    def build_plan(self) -> Dict[str, Any]:

        production_files = [
            file_path
            for file_path in self.files
            if not self._is_test_file(
                file_path
            )
        ]

        test_files = [
            file_path
            for file_path in self.files
            if self._is_test_file(
                file_path
            )
        ]

        migration_candidates = [
            file_path
            for file_path in production_files
            if self._is_python2(
                file_path
            )
        ]

        migration_order, cycles = (
            self._dependency_first_order(
                migration_candidates
            )
        )

        units = []

        for index, file_path in enumerate(
            migration_order,
            start=1
        ):

            units.append(
                self._build_unit(
                    file_path=file_path,
                    order=index,
                    migration_candidates=(
                        migration_candidates
                    ),
                    test_files=test_files,
                )
            )

        skipped = [
            {
                "file": file_path,
                "reason": self._skip_reason(
                    file_path
                ),
            }
            for file_path in production_files
            if file_path
            not in migration_candidates
        ]

        return {
            "repository": self.result.get(
                "repository"
            ),

            "source_language": "Python 2",

            "target_language": "Python 3",

            "strategy": (
                "dependency_first"
            ),

            "summary": {
                "total_python_files": len(
                    self.files
                ),

                "production_files": len(
                    production_files
                ),

                "test_files": len(
                    test_files
                ),

                "migration_candidates": len(
                    migration_candidates
                ),

                "migration_units": len(
                    units
                ),

                "dependency_cycles": len(
                    cycles
                ),
            },

            "migration_order": migration_order,

            "units": units,

            "skipped": skipped,

            "cycles": cycles,

            "tests": test_files,
        }

    # ==================================================================
    # MIGRATION UNIT
    # ==================================================================

    def _build_unit(
        self,
        file_path: str,
        order: int,
        migration_candidates: List[str],
        test_files: List[str],
    ) -> Dict[str, Any]:

        dependencies = (
            self._get_dependencies(
                file_path
            )
        )

        dependents = (
            self._get_dependents(
                file_path
            )
        )

        dependency_files = [
            edge["target"]
            for edge in dependencies
            if edge.get(
                "target"
            ) in migration_candidates
        ]

        dependent_files = [
            edge["source"]
            for edge in dependents
            if edge.get(
                "source"
            ) in migration_candidates
        ]

        related_tests = (
            self._related_tests(
                file_path,
                test_files
            )
        )

        reasons = (
            self.metadata
            .get(
                file_path,
                {}
            )
            .get(
                "migration_reasons",
                []
            )
        )

        risk_score = (
            self._risk_score(
                file_path=file_path,
                dependencies=dependencies,
                dependents=dependents,
                reasons=reasons,
                related_tests=related_tests,
            )
        )

        return {
            "order": order,

            "file": file_path,

            "version": self.metadata.get(
                file_path,
                {}
            ).get(
                "version",
                "Ambiguous"
            ),

            "dependencies": sorted(
                set(
                    dependency_files
                )
            ),

            "dependents": sorted(
                set(
                    dependent_files
                )
            ),

            "dependency_details": (
                self._format_edges(
                    dependencies
                )
            ),

            "dependent_details": (
                self._format_edges(
                    dependents
                )
            ),

            "related_tests": related_tests,

            "migration_reasons": reasons,

            "risk": self._risk_label(
                risk_score
            ),

            "risk_score": risk_score,

            "migration_notes": (
                self._migration_notes(
                    reasons
                )
            ),
        }

    # ==================================================================
    # DEPENDENCY ORDER
    # ==================================================================

    def _dependency_first_order(
        self,
        candidates: List[str]
    ):

        candidate_set = set(
            candidates
        )

        # A -> B means A depends on B.
        #
        # For migration order:
        #
        # B must appear before A.
        #
        # We therefore calculate indegree using the reversed
        # migration relationship.

        dependencies = {
            file_path: set()
            for file_path in candidates
        }

        for source in candidates:

            for edge in self.graph.get(
                source,
                []
            ):

                target = edge.get(
                    "target"
                )

                if target in candidate_set:

                    dependencies[
                        source
                    ].add(
                        target
                    )

        remaining = {
            file_path: set(
                deps
            )
            for file_path, deps
            in dependencies.items()
        }

        order = []

        while remaining:

            ready = sorted(
                file_path
                for file_path, deps
                in remaining.items()
                if not deps
            )

            if not ready:

                # Cycle exists.
                cycle_nodes = sorted(
                    remaining.keys()
                )

                # Break cycle deterministically.
                chosen = cycle_nodes[0]

                order.append(
                    chosen
                )

                del remaining[
                    chosen
                ]

                for deps in remaining.values():

                    deps.discard(
                        chosen
                    )

                continue

            for file_path in ready:

                order.append(
                    file_path
                )

                del remaining[
                    file_path
                ]

                for deps in remaining.values():

                    deps.discard(
                        file_path
                    )

        cycles = self._detect_cycles(
            dependencies
        )

        return order, cycles

    # ==================================================================
    # CYCLE DETECTION
    # ==================================================================

    def _detect_cycles(
        self,
        graph: Dict[
            str,
            Set[str]
        ]
    ) -> List[List[str]]:

        visited = set()
        stack = []
        stack_set = set()
        cycles = []

        def dfs(node):

            if node in stack_set:

                try:
                    start = stack.index(
                        node
                    )
                    cycle = stack[
                        start:
                    ] + [node]

                    normalized = sorted(
                        set(cycle)
                    )

                    if normalized not in cycles:
                        cycles.append(
                            normalized
                        )

                except ValueError:
                    pass

                return

            if node in visited:
                return

            visited.add(
                node
            )

            stack.append(
                node
            )

            stack_set.add(
                node
            )

            for dependency in graph.get(
                node,
                set()
            ):

                dfs(
                    dependency
                )

            stack.pop()

            stack_set.remove(
                node
            )

        for node in graph:

            dfs(
                node
            )

        return cycles

    # ==================================================================
    # DEPENDENCIES
    # ==================================================================

    def _get_dependencies(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:

        return list(
            self.graph.get(
                file_path,
                []
            )
        )

    def _get_dependents(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:

        return list(
            self.reverse_graph.get(
                file_path,
                []
            )
        )

    # ==================================================================
    # TESTS
    # ==================================================================

    def _related_tests(
        self,
        file_path: str,
        test_files: List[str]
    ) -> List[str]:

        result = []

        direct_dependents = {
            edge.get(
                "source"
            )
            for edge in self.reverse_graph.get(
                file_path,
                []
            )
        }

        stem = Path(
            file_path
        ).stem.lower()

        for test_file in test_files:

            if test_file in direct_dependents:

                result.append(
                    test_file
                )
                continue

            test_name = Path(
                test_file
            ).stem.lower()

            if stem in test_name:

                result.append(
                    test_file
                )

        return sorted(
            set(result)
        )

    # ==================================================================
    # RISK
    # ==================================================================

    def _risk_score(
        self,
        file_path: str,
        dependencies: List[Dict[str, Any]],
        dependents: List[Dict[str, Any]],
        reasons: List[str],
        related_tests: List[str],
    ) -> int:

        score = 0

        # Python 2 indicators.
        score += min(
            len(reasons) * 10,
            40
        )

        # Number of dependencies.
        score += min(
            len(
                {
                    edge.get(
                        "target"
                    )
                    for edge in dependencies
                }
            ) * 5,
            20
        )

        # Number of dependents.
        score += min(
            len(
                {
                    edge.get(
                        "source"
                    )
                    for edge in dependents
                }
            ) * 8,
            25
        )

        # Tests make the file more important,
        # but also give us a verification path.
        if related_tests:
            score += 5

        # Core modules with many relationships are
        # inherently more migration-sensitive.
        if len(dependents) >= 5:
            score += 10

        return min(
            score,
            100
        )

    @staticmethod
    def _risk_label(
        score: int
    ) -> str:

        if score >= 70:
            return "high"

        if score >= 35:
            return "medium"

        return "low"

    # ==================================================================
    # MIGRATION NOTES
    # ==================================================================

    @staticmethod
    def _migration_notes(
        reasons: List[str]
    ) -> List[str]:

        mapping = {
            "print_statement": (
                "Convert Python 2 print statements "
                "to Python 3 print() calls."
            ),

            "xrange": (
                "Replace xrange with range."
            ),

            "raw_input": (
                "Replace raw_input with input."
            ),

            "iteritems": (
                "Replace dict.iteritems() with "
                "dict.items() where appropriate."
            ),

            "iterkeys": (
                "Replace dict.iterkeys() with "
                "dict.keys() or direct iteration."
            ),

            "itervalues": (
                "Replace dict.itervalues() with "
                "dict.values() where appropriate."
            ),

            "basestring": (
                "Replace basestring checks with "
                "str/bytes-aware Python 3 logic."
            ),

            "unicode": (
                "Review unicode handling and convert "
                "to Python 3 string semantics."
            ),

            "long": (
                "Python 3 unifies int and long."
            ),

            "execfile": (
                "Replace execfile with explicit "
                "file reading and exec or another "
                "appropriate mechanism."
            ),

            "raw_urllib": (
                "Review urllib2 usage and migrate "
                "to Python 3 urllib modules."
            ),

            "cStringIO": (
                "Replace cStringIO with io.StringIO "
                "or io.BytesIO as appropriate."
            ),

            "ConfigParser": (
                "Replace ConfigParser with configparser."
            ),

            "old_raise": (
                "Convert Python 2 raise syntax."
            ),

            "old_except": (
                "Convert Python 2 exception binding syntax."
            ),

            "has_key": (
                "Replace has_key() with membership "
                "testing using 'in'."
            ),

            "unicode_literal": (
                "Review Python 2 unicode literal usage."
            ),
        }

        return [
            mapping[reason]
            for reason in reasons
            if reason in mapping
        ]

    # ==================================================================
    # FILTERING
    # ==================================================================

    def _is_python2(
        self,
        file_path: str
    ) -> bool:

        version = self.metadata.get(
            file_path,
            {}
        ).get(
            "version"
        )

        return version == "Python 2"

    @staticmethod
    def _is_test_file(
        file_path: str
    ) -> bool:

        normalized = file_path.lower()

        name = Path(
            normalized
        ).name

        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or normalized.startswith("tests/")
            or "/tests/" in normalized
        )

    def _skip_reason(
        self,
        file_path: str
    ) -> str:

        metadata = self.metadata.get(
            file_path,
            {}
        )

        version = metadata.get(
            "version",
            "Ambiguous"
        )

        if version == "Python 3":
            return "Already detected as Python 3."

        if self._is_test_file(
            file_path
        ):
            return "Test file handled separately."

        return (
            "Python version is ambiguous; "
            "requires manual review."
        )

    # ==================================================================
    # FORMATTING
    # ==================================================================

    @staticmethod
    def _format_edges(
        edges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        return [
            {
                "source": edge.get(
                    "source"
                ),
                "target": edge.get(
                    "target"
                ),
                "type": edge.get(
                    "type"
                ),
                "details": edge.get(
                    "details",
                    {}
                ),
            }
            for edge in edges
        ]

    # ==================================================================
    # SAVE
    # ==================================================================

    @staticmethod
    def save_plan(
        plan: Dict[str, Any],
        output_path: str
    ):

        output = Path(
            output_path
        ).resolve()

        output.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            output,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                plan,
                f,
                indent=2,
                ensure_ascii=False
            )