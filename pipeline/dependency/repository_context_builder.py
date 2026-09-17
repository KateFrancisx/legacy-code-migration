"""
Repository Context Builder

Builds focused, repository-aware context for one migration unit.

Flow:

MigrationPlanner
      ↓
Migration Unit
      ↓
RepositoryContextBuilder
      ↓
Structured Migration Context
      ↓
RAG / Prompt Builder
      ↓
LLM

The builder does NOT call the LLM and does NOT perform RAG.
Its job is to assemble the minimum useful repository context
required for migration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class RepositoryContextBuilder:
    """
    Build focused repository context for a migration unit.

    The builder uses the migration plan as the primary source of
    dependency information and reads source files only when needed.

    Important design principle:
        Do NOT send entire repositories or entire dependency files
        to the LLM when only a few symbols are relevant.
    """

    # Directories that should not appear in repository structure
    # or source discovery.
    IGNORED_DIRECTORIES = {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "virtualenv",
        "__pycache__",
        "node_modules",
        ".idea",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "dist",
        "build",
        "site-packages",
    }

    # Common files that should not be included in context discovery.
    IGNORED_FILES = {
        ".gitignore",
        ".gitattributes",
        ".DS_Store",
    }

    # Maximum amount of source we will attach for a dependency
    # when symbol extraction cannot isolate the requested code.
    MAX_FALLBACK_SOURCE_CHARS = 8000

    def __init__(
        self,
        repository_path: str,
        migration_plan: Dict[str, Any],
    ):
        self.repository_path = Path(
            repository_path
        ).resolve()

        self.migration_plan = migration_plan

        self.units: List[Dict[str, Any]] = (
            migration_plan.get("units", [])
        )

        self.total_units = len(self.units)

        # File -> migration unit
        self._unit_by_file: Dict[
            str,
            Dict[str, Any]
        ] = {}

        for unit in self.units:
            file_name = unit.get("file")

            if file_name:
                normalized = self._normalize_relative_path(
                    file_name
                )

                self._unit_by_file[normalized] = unit

        # Migration order as normalized paths.
        self.migration_order: List[str] = [
            self._normalize_relative_path(file_name)
            for file_name in migration_plan.get(
                "migration_order",
                []
            )
        ]

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    def build(
        self,
        target_file: str,
    ) -> Dict[str, Any]:
        """
        Build complete migration context for one target file.
        """

        target_file = self._normalize_relative_path(
            target_file
        )

        unit = self._find_unit(target_file)

        if unit is None:
            raise ValueError(
                f"Migration unit not found in plan: {target_file}"
            )

        target_source = self._read_file(
            target_file
        )

        dependencies = self._build_dependencies(
            unit
        )

        dependents = self._build_dependents(
            unit
        )

        related_tests = self._find_related_tests(
            unit,
            target_file,
        )

        relevant_source = self._build_relevant_source(
            dependencies
        )

        dependent_source = self._build_relevant_dependent_source(
            dependents
        )

        repository_structure = (
            self._build_repository_structure()
        )

        migration_state = (
            self._build_migration_state(
                target_file
            )
        )

        target_symbols = self._extract_symbols(
            target_source
        )

        context = {
            "repository": {
                "path": str(
                    self.repository_path
                ),
                "name": self.repository_path.name,
            },

            "target": {
                "file": target_file,
                "version": unit.get(
                    "version",
                    "Python 2",
                ),
                "source_code": target_source,
                "symbols": target_symbols,
            },

            "migration": {
                "source": self.migration_plan.get(
                    "source_language",
                    "Python 2",
                ),
                "target": self.migration_plan.get(
                    "target_language",
                    "Python 3",
                ),
                "strategy": self.migration_plan.get(
                    "strategy",
                    "dependency_first",
                ),
                "order": unit.get(
                    "order"
                ),
                "total_units": self.total_units,
                "reasons": unit.get(
                    "migration_reasons",
                    [],
                ),
                "risk": unit.get(
                    "risk",
                    "unknown",
                ),
                "risk_score": unit.get(
                    "risk_score"
                ),
                "migration_notes": unit.get(
                    "migration_notes",
                    [],
                ),
                "migration_order": self.migration_order,
                "state": migration_state,
            },

            "dependencies": dependencies,

            "dependents": dependents,

            "related_tests": related_tests,

            "relevant_source": relevant_source,

            "dependent_source": dependent_source,

            "repository_structure": repository_structure,
        }

        return context

    def build_all(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Build context for every migration unit.
        """

        contexts: List[
            Dict[str, Any]
        ] = []

        for unit in self.units:

            target_file = unit.get(
                "file"
            )

            if not target_file:
                continue

            try:
                contexts.append(
                    self.build(
                        target_file
                    )
                )

            except Exception as exc:

                print(
                    f"[WARN] Could not build context "
                    f"for {target_file}: {exc}"
                )

        return contexts

    # ==================================================================
    # MIGRATION UNIT
    # ==================================================================

    def _find_unit(
        self,
        target_file: str,
    ) -> Optional[
        Dict[str, Any]
    ]:

        normalized = (
            self._normalize_relative_path(
                target_file
            )
        )

        return self._unit_by_file.get(
            normalized
        )

    # ==================================================================
    # MIGRATION STATE
    # ==================================================================

    def _build_migration_state(
        self,
        target_file: str,
    ) -> Dict[str, Any]:
        """
        Describe where the current file sits in the migration sequence.
        """

        if target_file not in self.migration_order:

            return {
                "position": None,
                "total": self.total_units,
                "previous": [],
                "current": target_file,
                "next": [],
            }

        index = self.migration_order.index(
            target_file
        )

        previous = self.migration_order[
            :index
        ]

        next_files = self.migration_order[
            index + 1:
        ]

        return {
            "position": index + 1,
            "total": len(
                self.migration_order
            ),
            "previous": previous,
            "current": target_file,
            "next": next_files,
        }

    # ==================================================================
    # DEPENDENCIES
    # ==================================================================

    def _build_dependencies(
        self,
        unit: Dict[str, Any],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Build compact dependency information.

        We preserve:
            - dependency file
            - existence
            - relationship details
            - referenced symbols

        We intentionally DO NOT attach the entire dependency source here.
        Relevant source is extracted separately.
        """

        results: List[
            Dict[str, Any]
        ] = []

        dependency_files = unit.get(
            "dependencies",
            [],
        )

        dependency_details = unit.get(
            "dependency_details",
            [],
        )

        details_by_target: Dict[
            str,
            List[Dict[str, Any]]
        ] = {}

        for detail in dependency_details:

            target = detail.get(
                "target"
            )

            if not target:
                continue

            target = (
                self._normalize_relative_path(
                    target
                )
            )

            details_by_target.setdefault(
                target,
                [],
            ).append(
                detail
            )

        for dependency in dependency_files:

            dependency = (
                self._normalize_relative_path(
                    dependency
                )
            )

            source = (
                self._read_file_if_exists(
                    dependency
                )
            )

            relationships = (
                details_by_target.get(
                    dependency,
                    [],
                )
            )

            referenced_symbols = (
                self._extract_referenced_symbols(
                    relationships
                )
            )

            results.append(
                {
                    "file": dependency,
                    "exists": source is not None,
                    "referenced_symbols": (
                        referenced_symbols
                    ),
                    "relationships": (
                        relationships
                    ),
                }
            )

        return results

    # ==================================================================
    # DEPENDENTS
    # ==================================================================

    def _build_dependents(
        self,
        unit: Dict[str, Any],
    ) -> List[
        Dict[str, Any]
    ]:

        results: List[
            Dict[str, Any]
        ] = []

        dependent_files = unit.get(
            "dependents",
            [],
        )

        dependent_details = unit.get(
            "dependent_details",
            [],
        )

        details_by_source: Dict[
            str,
            List[Dict[str, Any]]
        ] = {}

        for detail in dependent_details:

            source = detail.get(
                "source"
            )

            if not source:
                continue

            source = (
                self._normalize_relative_path(
                    source
                )
            )

            details_by_source.setdefault(
                source,
                [],
            ).append(
                detail
            )

        for dependent in dependent_files:

            dependent = (
                self._normalize_relative_path(
                    dependent
                )
            )

            relationships = (
                details_by_source.get(
                    dependent,
                    [],
                )
            )

            referenced_symbols = (
                self._extract_referenced_symbols(
                    relationships
                )
            )

            results.append(
                {
                    "file": dependent,
                    "referenced_symbols": (
                        referenced_symbols
                    ),
                    "relationships": (
                        relationships
                    ),
                }
            )

        return results

    # ==================================================================
    # RELATED TESTS
    # ==================================================================

    def _find_related_tests(
        self,
        unit: Dict[str, Any],
        target_file: str,
    ) -> List[
        Dict[str, Any]
    ]:

        tests: List[
            Dict[str, Any]
        ] = []

        explicit_tests = unit.get(
            "related_tests",
            [],
        )

        # --------------------------------------------------------------
        # 1. Explicit tests from migration planner
        # --------------------------------------------------------------

        for test_file in explicit_tests:

            test_file = (
                self._normalize_relative_path(
                    test_file
                )
            )

            source = (
                self._read_file_if_exists(
                    test_file
                )
            )

            tests.append(
                {
                    "file": test_file,
                    "exists": source is not None,
                    "source_code": source,
                    "relation": "planner_related_test",
                }
            )

        if tests:
            return tests

        # --------------------------------------------------------------
        # 2. Infer from plan-level test list
        # --------------------------------------------------------------

        plan_tests = self.migration_plan.get(
            "tests",
            [],
        )

        target_stem = Path(
            target_file
        ).stem.lower()

        target_name_variants = {
            target_stem,
            target_stem.replace(
                "_",
                "",
            ),
        }

        for test_file in plan_tests:

            test_file = (
                self._normalize_relative_path(
                    test_file
                )
            )

            source = (
                self._read_file_if_exists(
                    test_file
                )
            )

            if source is None:
                continue

            test_lower = test_file.lower()
            source_lower = source.lower()

            relevant = False

            # File naming relation.
            for variant in target_name_variants:

                if variant and variant in test_lower:
                    relevant = True
                    break

            # Source reference relation.
            if not relevant:

                for variant in target_name_variants:

                    if variant and variant in source_lower:
                        relevant = True
                        break

            if relevant:

                tests.append(
                    {
                        "file": test_file,
                        "exists": True,
                        "source_code": source,
                        "relation": "inferred_test",
                    }
                )

        return tests

    # ==================================================================
    # RELEVANT DEPENDENCY SOURCE
    # ==================================================================

    def _build_relevant_source(
        self,
        dependencies: List[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Extract only relevant symbols from dependency files.

        Example:

            billing.py -> utils.py

            referenced:
                normalize_name
                calculate_percentage
                format_money

        Instead of sending all of utils.py, attempt to extract
        those specific definitions.
        """

        results: List[
            Dict[str, Any]
        ] = []

        for dependency in dependencies:

            if not dependency.get(
                "exists"
            ):
                continue

            file_name = dependency[
                "file"
            ]

            referenced_symbols = (
                dependency.get(
                    "referenced_symbols",
                    [],
                )
            )

            source = self._read_file_if_exists(
                file_name
            )

            if not source:
                continue

            extracted = (
                self._extract_relevant_symbols(
                    source,
                    referenced_symbols,
                )
            )

            # If extraction fails, use a bounded
            # fallback rather than dumping the
            # entire file.
            if not extracted:

                fallback = (
                    source[
                        :self.MAX_FALLBACK_SOURCE_CHARS
                    ]
                )

                extracted = fallback

            results.append(
                {
                    "file": file_name,
                    "referenced_symbols": (
                        referenced_symbols
                    ),
                    "source_code": extracted,
                }
            )

        return results

    # ==================================================================
    # RELEVANT DEPENDENT SOURCE
    # ==================================================================

    def _build_relevant_dependent_source(
        self,
        dependents: List[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Include compact source context for dependent files.

        We do not dump entire dependent files.

        Only functions/classes that directly reference the target
        are attempted to be extracted.
        """

        results: List[
            Dict[str, Any]
        ] = []

        for dependent in dependents:

            file_name = dependent.get(
                "file"
            )

            if not file_name:
                continue

            source = (
                self._read_file_if_exists(
                    file_name
                )
            )

            if not source:
                continue

            referenced_symbols = (
                dependent.get(
                    "referenced_symbols",
                    [],
                )
            )

            extracted = (
                self._extract_relevant_symbols(
                    source,
                    referenced_symbols,
                )
            )

            if not extracted:

                extracted = (
                    source[
                        :self.MAX_FALLBACK_SOURCE_CHARS
                    ]
                )

            results.append(
                {
                    "file": file_name,
                    "referenced_symbols": (
                        referenced_symbols
                    ),
                    "source_code": extracted,
                }
            )

        return results

    # ==================================================================
    # SYMBOL EXTRACTION
    # ==================================================================

    def _extract_referenced_symbols(
        self,
        relationships: List[
            Dict[str, Any]
        ],
    ) -> List[str]:
        """
        Extract symbol names from dependency relationships.
        """

        names: Set[str] = set()

        for relationship in relationships:

            details = relationship.get(
                "details",
                {},
            )

            imported_name = details.get(
                "name"
            )

            if imported_name:
                names.add(
                    imported_name
                )

            function_name = details.get(
                "function"
            )

            if function_name:
                names.add(
                    function_name
                )

            class_name = details.get(
                "class"
            )

            if class_name:
                names.add(
                    class_name
                )

        return sorted(names)

    def _extract_symbols(
        self,
        source: str,
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Lightweight Python symbol extraction.

        This is intentionally parser-independent.
        The dependency analyzer already performs structural analysis.

        We use this only to make the context useful to the prompt layer.
        """

        symbols: List[
            Dict[str, Any]
        ] = []

        lines = source.splitlines()

        class_stack: List[
            tuple[int, str]
        ] = []

        for index, line in enumerate(
            lines,
            start=1,
        ):

            stripped = line.lstrip()

            if not stripped:
                continue

            indentation = (
                len(line)
                - len(stripped)
            )

            # Remove classes that are no longer enclosing.
            while (
                class_stack
                and indentation
                <= class_stack[-1][0]
            ):
                class_stack.pop()

            class_match = re.match(
                r"class\s+([A-Za-z_]\w*)",
                stripped,
            )

            if class_match:

                name = class_match.group(
                    1
                )

                symbols.append(
                    {
                        "type": "class",
                        "name": name,
                        "line": index,
                    }
                )

                class_stack.append(
                    (
                        indentation,
                        name,
                    )
                )

                continue

            function_match = re.match(
                r"(?:async\s+)?def\s+([A-Za-z_]\w*)",
                stripped,
            )

            if function_match:

                name = function_match.group(
                    1
                )

                enclosing_class = (
                    class_stack[-1][1]
                    if class_stack
                    else None
                )

                symbols.append(
                    {
                        "type": "method"
                        if enclosing_class
                        else "function",
                        "name": name,
                        "line": index,
                        "class": enclosing_class,
                    }
                )

        return symbols

    def _extract_relevant_symbols(
        self,
        source: str,
        symbol_names: List[str],
    ) -> str:
        """
        Extract definitions matching requested symbol names.

        Supports normal Python function/method/class definitions.

        This intentionally uses source-level extraction so it remains
        tolerant of Python 2 syntax.
        """

        if not symbol_names:
            return ""

        wanted = set(
            symbol_names
        )

        lines = source.splitlines()

        blocks: List[
            str
        ] = []

        current_start: Optional[
            int
        ] = None

        current_indent: Optional[
            int
        ] = None

        current_name: Optional[
            str
        ] = None

        def flush(
            end_index: int,
        ) -> None:

            nonlocal current_start
            nonlocal current_indent
            nonlocal current_name

            if (
                current_start is None
                or current_name is None
            ):
                return

            block = "\n".join(
                lines[
                    current_start:end_index
                ]
            )

            blocks.append(
                block
            )

            current_start = None
            current_indent = None
            current_name = None

        for index, line in enumerate(
            lines
        ):

            stripped = line.lstrip()

            if not stripped:
                continue

            indentation = (
                len(line)
                - len(stripped)
            )

            match = re.match(
                r"(?:async\s+)?def\s+([A-Za-z_]\w*)",
                stripped,
            )

            class_match = re.match(
                r"class\s+([A-Za-z_]\w*)",
                stripped,
            )

            definition_match = (
                match or class_match
            )

            if definition_match:

                name = definition_match.group(
                    1
                )

                # Any new top-level/same-level definition
                # closes the previous definition.
                if (
                    current_start is not None
                    and current_indent is not None
                    and indentation
                    <= current_indent
                ):
                    flush(index)

                if name in wanted:

                    current_start = index
                    current_indent = indentation
                    current_name = name

                continue

            if current_start is not None:

                if (
                    indentation
                    <= current_indent
                ):
                    # A new statement at the same or
                    # lower indentation ends the block.
                    flush(index)

        flush(
            len(lines)
        )

        if not blocks:
            return ""

        return "\n\n".join(
            blocks
        )

    # ==================================================================
    # REPOSITORY STRUCTURE
    # ==================================================================

    def _build_repository_structure(
        self,
    ) -> List[str]:
        """
        Return repository file structure.

        Only files are returned.
        Ignored directories are skipped.
        """

        structure: List[
            str
        ] = []

        if not self.repository_path.exists():
            return structure

        for path in sorted(
            self.repository_path.rglob("*")
        ):

            relative = path.relative_to(
                self.repository_path
            )

            if any(
                part in self.IGNORED_DIRECTORIES
                for part in relative.parts
            ):
                continue

            if (
                path.is_file()
                and path.name not in self.IGNORED_FILES
            ):

                structure.append(
                    str(relative).replace(
                        "\\",
                        "/",
                    )
                )

        return structure

    # ==================================================================
    # FILE HELPERS
    # ==================================================================

    def _normalize_relative_path(
        self,
        path: str,
    ) -> str:
        """
        Normalize Windows/Linux relative paths.
        """

        normalized = str(
            path
        ).replace(
            "\\",
            "/",
        )

        # Remove leading ./ repeatedly.
        while normalized.startswith(
            "./"
        ):
            normalized = normalized[
                2:
            ]

        return normalized.lstrip(
            "/"
        )

    def _read_file(
        self,
        relative_path: str,
    ) -> str:
        """
        Read a repository file.
        """

        relative_path = (
            self._normalize_relative_path(
                relative_path
            )
        )

        path = (
            self.repository_path
            / relative_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"File does not exist: {path}"
            )

        if not path.is_file():
            raise FileNotFoundError(
                f"Path is not a file: {path}"
            )

        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    def _read_file_if_exists(
        self,
        relative_path: str,
    ) -> Optional[str]:
        """
        Safely read a repository file.
        """

        relative_path = (
            self._normalize_relative_path(
                relative_path
            )
        )

        path = (
            self.repository_path
            / relative_path
        )

        if (
            not path.exists()
            or not path.is_file()
        ):
            return None

        try:

            return path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        except Exception:

            return None


# ======================================================================
# CONVENIENCE HELPERS
# ======================================================================

def load_migration_plan(
    plan_path: str,
) -> Dict[str, Any]:
    """
    Load migration plan JSON.
    """

    with open(
        plan_path,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


def build_repository_context(
    repository_path: str,
    plan_path: str,
    target_file: str,
) -> Dict[str, Any]:
    """
    Convenience function for building context from a saved plan.
    """

    plan = load_migration_plan(
        plan_path
    )

    builder = RepositoryContextBuilder(
        repository_path=repository_path,
        migration_plan=plan,
    )

    return builder.build(
        target_file
    )