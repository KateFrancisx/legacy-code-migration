from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class DependencyAnalyzer:
    """
    Generic repository-level dependency analyzer for Python 2/3 code.

    Dependency direction:

        A -> B

    means:

        A depends on B.

    Example:

        main.py -> billing.py

    means main.py depends on billing.py.

    The analyzer is repository-agnostic.

    It discovers:

        - Python files
        - modules
        - functions
        - classes
        - imports
        - from-imports
        - function calls
        - inheritance
        - reverse dependencies
        - Python 2 migration indicators

    Parso is used because Python's built-in ast module cannot reliably
    parse Python 2 syntax on a Python 3 runtime.
    """

    NOISE_DIRECTORIES = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "dist",
        "build",
        "site-packages",
        ".idea",
        ".vscode",
    }

    PYTHON_EXTENSIONS = {
        ".py",
        ".pyw",
    }

    PYTHON2_PATTERNS = {
        "print_statement": re.compile(
            r"(?m)^\s*print\s+[^(\n]"
        ),
        "xrange": re.compile(
            r"\bxrange\s*\("
        ),
        "raw_input": re.compile(
            r"\braw_input\s*\("
        ),
        "iteritems": re.compile(
            r"\.iteritems\s*\("
        ),
        "iterkeys": re.compile(
            r"\.iterkeys\s*\("
        ),
        "itervalues": re.compile(
            r"\.itervalues\s*\("
        ),
        "basestring": re.compile(
            r"\bbasestring\b"
        ),
        "unicode": re.compile(
            r"\bunicode\b"
        ),
        "long": re.compile(
            r"\blong\s*\("
        ),
        "execfile": re.compile(
            r"\bexecfile\s*\("
        ),
        "raw_urllib": re.compile(
            r"\burllib2\b"
        ),
        "cStringIO": re.compile(
            r"\bcStringIO\b"
        ),
        "ConfigParser": re.compile(
            r"\bConfigParser\b"
        ),
        "old_raise": re.compile(
            r"(?m)^\s*raise\s+\w+\s*,"
        ),
        "old_except": re.compile(
            r"(?m)^\s*except\s+\w+\s*,\s*\w+\s*:"
        ),
        "has_key": re.compile(
            r"\.has_key\s*\("
        ),
        "unicode_literal": re.compile(
            r"(?<!\w)u(['\"])"
        ),
    }

    PYTHON3_PATTERNS = {
        "f_string": re.compile(
            r"""(?<![\w])f(['"])"""
        ),
        "async_def": re.compile(
            r"\basync\s+def\b"
        ),
        "await": re.compile(
            r"\bawait\b"
        ),
    }

    BUILTIN_CALLS = {
        "abs",
        "all",
        "any",
        "bool",
        "bytes",
        "callable",
        "chr",
        "dict",
        "dir",
        "divmod",
        "enumerate",
        "eval",
        "filter",
        "float",
        "format",
        "getattr",
        "hasattr",
        "hash",
        "hex",
        "id",
        "input",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "pow",
        "print",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
    }

    KEYWORD_CALLS = {
        "if",
        "elif",
        "else",
        "for",
        "while",
        "with",
        "try",
        "except",
        "finally",
        "return",
        "yield",
        "lambda",
        "class",
        "def",
        "assert",
        "raise",
        "del",
        "pass",
        "break",
        "continue",
        "import",
        "from",
    }

    def __init__(self, repo_path: str):

        self.repo_path = Path(
            repo_path
        ).resolve()

        if not self.repo_path.is_dir():
            raise ValueError(
                f"Repository does not exist: "
                f"{self.repo_path}"
            )

        self.files: List[str] = []

        # module -> file
        self.module_to_file: Dict[
            str,
            str
        ] = {}

        # file -> aggregated target relationships
        self._graph: Dict[
            str,
            Dict[str, Dict[str, Any]]
        ] = defaultdict(dict)

        # file -> reverse relationships
        self._reverse_graph: Dict[
            str,
            Dict[str, Dict[str, Any]]
        ] = defaultdict(dict)

        # file -> symbols
        self.symbols: Dict[
            str,
            List[Dict[str, Any]]
        ] = defaultdict(list)

        # file -> source
        self.sources: Dict[
            str,
            str
        ] = {}

        # file -> imports
        self.imports: Dict[
            str,
            List[Dict[str, Any]]
        ] = defaultdict(list)

        # file -> from imports
        self.from_imports: Dict[
            str,
            List[Dict[str, Any]]
        ] = defaultdict(list)

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    def analyze(self) -> Dict[str, Any]:

        self._reset()

        self.files = self._discover_python_files()

        self._load_sources()

        self._build_module_index()

        # --------------------------------------------------------------
        # Pass 1: symbols
        # --------------------------------------------------------------

        for file_path in self.files:
            self._extract_symbols(
                file_path
            )

        # --------------------------------------------------------------
        # Pass 2: imports
        # --------------------------------------------------------------

        for file_path in self.files:
            self._extract_imports(
                file_path
            )

        # --------------------------------------------------------------
        # Pass 3: function calls
        # --------------------------------------------------------------

        for file_path in self.files:
            self._extract_function_calls(
                file_path
            )

        # --------------------------------------------------------------
        # Pass 4: inheritance
        # --------------------------------------------------------------

        for file_path in self.files:
            self._extract_inheritance(
                file_path
            )

        # --------------------------------------------------------------
        # Reverse graph
        # --------------------------------------------------------------

        self._build_reverse_graph()

        edges = self._build_edges()

        graph = self._build_public_graph(
            edges
        )

        reverse_graph = (
            self._build_public_reverse_graph()
        )

        statistics = (
            self._build_statistics(
                edges
            )
        )

        return {
            "repository": str(
                self.repo_path
            ),

            "files": list(
                self.files
            ),

            "file_count": len(
                self.files
            ),

            "modules": dict(
                self.module_to_file
            ),

            # Test/context-builder compatible.
            "graph": graph,

            # Rich adjacency representation.
            "dependency_graph": (
                self._serialize_dependency_graph()
            ),

            "adjacency_graph": (
                self._serialize_dependency_graph()
            ),

            "reverse_graph": reverse_graph,

            "edges": edges,

            "symbols": {
                file_path: list(
                    self.symbols.get(
                        file_path,
                        []
                    )
                )
                for file_path in self.files
            },

            "file_metadata": (
                self._build_file_metadata()
            ),

            "statistics": statistics,
        }

    # ==================================================================
    # RESET
    # ==================================================================

    def _reset(self):

        self.files = []

        self.module_to_file = {}

        self._graph = defaultdict(dict)

        self._reverse_graph = defaultdict(dict)

        self.symbols = defaultdict(list)

        self.sources = {}

        self.imports = defaultdict(list)

        self.from_imports = defaultdict(list)

    # ==================================================================
    # FILE DISCOVERY
    # ==================================================================

    def _discover_python_files(self) -> List[str]:

        result = []

        for root, dirs, files in os.walk(
            self.repo_path
        ):

            dirs[:] = [
                directory
                for directory in dirs
                if directory
                not in self.NOISE_DIRECTORIES
            ]

            for filename in files:

                extension = (
                    Path(filename)
                    .suffix
                    .lower()
                )

                if extension not in self.PYTHON_EXTENSIONS:
                    continue

                absolute = (
                    Path(root)
                    / filename
                )

                relative = (
                    absolute.relative_to(
                        self.repo_path
                    )
                    .as_posix()
                )

                result.append(
                    relative
                )

        return sorted(
            set(result)
        )

    # ==================================================================
    # SOURCE
    # ==================================================================

    def _load_sources(self):

        for file_path in self.files:

            absolute = (
                self.repo_path
                / file_path
            )

            try:

                self.sources[
                    file_path
                ] = absolute.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

            except OSError:

                self.sources[
                    file_path
                ] = ""

    # ==================================================================
    # MODULE INDEX
    # ==================================================================

    def _build_module_index(self):

        for file_path in self.files:

            module = (
                self._module_name(
                    file_path
                )
            )

            if module:
                self.module_to_file[
                    module
                ] = file_path

            for variant in (
                self._module_variants(
                    file_path
                )
            ):

                if variant:
                    self.module_to_file.setdefault(
                        variant,
                        file_path
                    )

    def _module_name(
        self,
        file_path: str
    ) -> str:

        normalized = file_path.replace(
            "\\",
            "/"
        )

        if normalized.endswith(
            ".pyw"
        ):
            normalized = normalized[:-4]

        elif normalized.endswith(
            ".py"
        ):
            normalized = normalized[:-3]

        parts = normalized.split("/")

        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        return ".".join(
            part
            for part in parts
            if part
        )

    def _module_variants(
        self,
        file_path: str
    ) -> List[str]:

        normalized = file_path.replace(
            "\\",
            "/"
        )

        module = self._module_name(
            file_path
        )

        result = []

        if module:
            result.append(
                module
            )

            parts = module.split(
                "."
            )

            if parts:
                result.append(
                    parts[-1]
                )

        filename = Path(
            normalized
        ).stem

        if filename != "__init__":
            result.append(
                filename
            )

        return list(
            dict.fromkeys(
                result
            )
        )

    # ==================================================================
    # SYMBOL EXTRACTION
    # ==================================================================

    def _extract_symbols(
        self,
        file_path: str
    ):

        source = self.sources.get(
            file_path,
            ""
        )

        if not source:
            return

        try:

            import parso

            version = self._detect_version(
                source
            )

            grammar_version = (
                "2.7"
                if version == "Python 2"
                else "3.8"
            )

            grammar = parso.load_grammar(
                version=grammar_version
            )

            tree = grammar.parse(
                source,
                error_recovery=True
            )

            self._walk_symbol_nodes(
                file_path,
                tree
            )

        except Exception:

            # Regex fallback keeps the analyzer
            # operational if Parso encounters
            # unusual legacy syntax.

            self._regex_symbols(
                file_path,
                source
            )

    def _walk_symbol_nodes(
        self,
        file_path: str,
        node
    ):

        node_type = getattr(
            node,
            "type",
            None
        )

        if node_type in {
            "funcdef",
            "async_funcdef",
        }:

            name = self._node_name(
                node
            )

            if name:

                self._add_symbol(
                    file_path,
                    {
                        "type": "function",
                        "name": name,
                        "line": self._line(
                            node
                        ),
                    }
                )

        elif node_type == "classdef":

            name = self._node_name(
                node
            )

            if name:

                self._add_symbol(
                    file_path,
                    {
                        "type": "class",
                        "name": name,
                        "line": self._line(
                            node
                        ),
                    }
                )

        for child in getattr(
            node,
            "children",
            []
        ):

            self._walk_symbol_nodes(
                file_path,
                child
            )

    def _regex_symbols(
        self,
        file_path: str,
        source: str
    ):

        pattern = re.compile(
            r"(?m)^[ \t]*(?:async\s+)?def\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
        )

        for match in pattern.finditer(
            source
        ):

            line = (
                source.count(
                    "\n",
                    0,
                    match.start()
                )
                + 1
            )

            self._add_symbol(
                file_path,
                {
                    "type": "function",
                    "name": match.group(1),
                    "line": line,
                }
            )

        pattern = re.compile(
            r"(?m)^[ \t]*class\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
        )

        for match in pattern.finditer(
            source
        ):

            line = (
                source.count(
                    "\n",
                    0,
                    match.start()
                )
                + 1
            )

            self._add_symbol(
                file_path,
                {
                    "type": "class",
                    "name": match.group(1),
                    "line": line,
                }
            )

    def _add_symbol(
        self,
        file_path: str,
        symbol: Dict[str, Any]
    ):

        existing = {
            (
                item.get("type"),
                item.get("name"),
                item.get("line"),
            )
            for item in self.symbols[
                file_path
            ]
        }

        key = (
            symbol.get("type"),
            symbol.get("name"),
            symbol.get("line"),
        )

        if key not in existing:

            self.symbols[
                file_path
            ].append(
                symbol
            )

    # ==================================================================
    # IMPORT EXTRACTION
    # ==================================================================

    def _extract_imports(
        self,
        file_path: str
    ):

        source = self.sources.get(
            file_path,
            ""
        )

        if not source:
            return

        # --------------------------------------------------------------
        # Use source-level matching.
        #
        # This is more tolerant of Python 2 syntax than relying only
        # on a particular Parso node representation.
        # --------------------------------------------------------------

        lines = source.splitlines()

        i = 0

        while i < len(lines):

            line = lines[i]

            stripped = line.strip()

            line_number = i + 1

            # ----------------------------------------------------------
            # from X import ...
            # ----------------------------------------------------------

            from_match = re.match(
                r"^from\s+([.\w]+)\s+import\s+(.+)$",
                stripped
            )

            if from_match:

                module = from_match.group(
                    1
                )

                imported_part = from_match.group(
                    2
                )

                # Multiline imports.
                if (
                    "(" in imported_part
                    and ")"
                    not in imported_part
                ):

                    collected = [
                        imported_part
                    ]

                    j = i + 1

                    while j < len(lines):

                        collected.append(
                            lines[j]
                        )

                        if ")" in lines[j]:
                            break

                        j += 1

                    imported_part = " ".join(
                        collected
                    )

                    i = j

                self._process_from_import(
                    file_path=file_path,
                    module=module,
                    imported_part=imported_part,
                    line_number=line_number,
                )

                i += 1
                continue

            # ----------------------------------------------------------
            # import X, Y
            # ----------------------------------------------------------

            import_match = re.match(
                r"^import\s+(.+)$",
                stripped
            )

            if import_match:

                imported_part = (
                    import_match.group(1)
                )

                self._process_import(
                    file_path=file_path,
                    imported_part=imported_part,
                    line_number=line_number,
                )

            i += 1

    def _process_import(
        self,
        file_path: str,
        imported_part: str,
        line_number: int
    ):

        imported_part = (
            imported_part.split(
                "#",
                1
            )[0]
        )

        for item in imported_part.split(
            ","
        ):

            item = item.strip()

            if not item:
                continue

            match = re.match(
                r"^([A-Za-z_][\w.]*)"
                r"(?:\s+as\s+([A-Za-z_]\w*))?$",
                item
            )

            if not match:
                continue

            module = match.group(
                1
            )

            alias = match.group(
                2
            )

            target = self._resolve_module(
                module
            )

            if not target:
                continue

            details = {
                "module": module,
                "alias": alias,
                "line": line_number,
            }

            self.imports[
                file_path
            ].append(
                details
            )

            self._add_edge(
                source=file_path,
                target=target,
                edge_type="import",
                details=details,
            )

    def _process_from_import(
        self,
        file_path: str,
        module: str,
        imported_part: str,
        line_number: int
    ):

        module = module.strip()

        imported_part = (
            imported_part
            .replace("(", "")
            .replace(")", "")
        )

        imported_part = (
            imported_part.split(
                "#",
                1
            )[0]
        )

        target = self._resolve_module(
            module,
            current_file=file_path
        )

        if not target:
            return

        for item in imported_part.split(
            ","
        ):

            item = item.strip()

            if not item:
                continue

            if item == "*":

                name = "*"
                alias = None

            else:

                match = re.match(
                    r"^([A-Za-z_][\w]*)"
                    r"(?:\s+as\s+([A-Za-z_]\w*))?$",
                    item
                )

                if not match:
                    continue

                name = match.group(
                    1
                )

                alias = match.group(
                    2
                )

            details = {
                "module": module,
                "name": name,
                "alias": alias,
                "line": line_number,
            }

            self.from_imports[
                file_path
            ].append(
                details
            )

            self._add_edge(
                source=file_path,
                target=target,
                edge_type="from_import",
                details=details,
            )

    # ==================================================================
    # MODULE RESOLUTION
    # ==================================================================

    def _resolve_module(
        self,
        module: str,
        current_file: Optional[str] = None
    ) -> Optional[str]:

        if not module:
            return None

        module = module.strip()

        # --------------------------------------------------------------
        # Relative import.
        # --------------------------------------------------------------

        if module.startswith("."):

            module = self._resolve_relative_module(
                module,
                current_file
            )

        if not module:
            return None

        # Exact match.
        if module in self.module_to_file:

            return self.module_to_file[
                module
            ]

        # Progressive package match.
        parts = module.split(".")

        for length in range(
            len(parts),
            0,
            -1
        ):

            candidate = ".".join(
                parts[:length]
            )

            if candidate in self.module_to_file:

                return self.module_to_file[
                    candidate
                ]

        # Basename fallback.
        basename = parts[-1]

        matches = []

        for file_path in self.files:

            if Path(
                file_path
            ).stem == basename:

                matches.append(
                    file_path
                )

        if len(matches) == 1:
            return matches[0]

        return None

    def _resolve_relative_module(
        self,
        module: str,
        current_file: Optional[str]
    ) -> str:

        if not current_file:
            return module.lstrip(".")

        dots = 0

        while (
            dots < len(module)
            and module[dots] == "."
        ):
            dots += 1

        remainder = module[
            dots:
        ]

        current_module = self._module_name(
            current_file
        )

        parts = current_module.split(
            "."
        ) if current_module else []

        # One dot = current package.
        levels_up = max(
            dots - 1,
            0
        )

        if levels_up:

            parts = parts[
                : max(
                    0,
                    len(parts) - levels_up
                )
            ]

        if remainder:

            parts.extend(
                remainder.split(".")
            )

        return ".".join(
            part
            for part in parts
            if part
        )

    # ==================================================================
    # FUNCTION CALLS
    # ==================================================================

    def _extract_function_calls(
        self,
        file_path: str
    ):

        source = self.sources.get(
            file_path,
            ""
        )

        if not source:
            return

        # --------------------------------------------------------------
        # Map imported names to target files.
        #
        # Example:
        #
        # from billing import build_invoice
        #
        # gives:
        #
        # build_invoice -> billing.py
        # --------------------------------------------------------------

        imported_functions = {}

        for edge in self._edges_for_source(
            file_path
        ):

            if edge["type"] != "from_import":
                continue

            details = edge.get(
                "details",
                {}
            )

            name = details.get(
                "name"
            )

            if name and name != "*":

                imported_functions[
                    details.get(
                        "alias"
                    ) or name
                ] = edge[
                    "target"
                ]

        # import module as alias.
        imported_modules = {}

        for edge in self._edges_for_source(
            file_path
        ):

            if edge["type"] != "import":
                continue

            details = edge.get(
                "details",
                {}
            )

            module = details.get(
                "module"
            )

            if module:

                alias = (
                    details.get(
                        "alias"
                    )
                    or module.split(
                        "."
                    )[-1]
                )

                imported_modules[
                    alias
                ] = edge[
                    "target"
                ]

        # --------------------------------------------------------------
        # Every function defined in repository.
        # --------------------------------------------------------------

        functions_by_name = defaultdict(
            list
        )

        for target_file in self.files:

            for symbol in self.symbols.get(
                target_file,
                []
            ):

                if symbol.get(
                    "type"
                ) != "function":
                    continue

                functions_by_name[
                    symbol.get(
                        "name"
                    )
                ].append(
                    target_file
                )

        # --------------------------------------------------------------
        # Detect calls.
        #
        # name(...)
        # module.name(...)
        # --------------------------------------------------------------

        call_pattern = re.compile(
            r"(?<![\w.])"
            r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)"
            r"\s*\("
        )

        for match in call_pattern.finditer(
            source
        ):

            expression = match.group(
                1
            )

            line_number = (
                source.count(
                    "\n",
                    0,
                    match.start()
                )
                + 1
            )

            # Skip definitions.
            line_start = source.rfind(
                "\n",
                0,
                match.start()
            ) + 1

            prefix = source[
                line_start:
                match.start()
            ].strip()

            if re.search(
                r"\bdef\s*$",
                prefix
            ):
                continue

            simple_name = expression.split(
                "."
            )[-1]

            if simple_name in (
                self.KEYWORD_CALLS
                | self.BUILTIN_CALLS
            ):
                continue

            target = None

            # ----------------------------------------------------------
            # Imported function.
            # ----------------------------------------------------------

            if expression in imported_functions:

                target = imported_functions[
                    expression
                ]

            # ----------------------------------------------------------
            # module.function()
            # ----------------------------------------------------------

            elif "." in expression:

                module_alias, function_name = (
                    expression.split(
                        ".",
                        1
                    )
                )

                module_file = (
                    imported_modules.get(
                        module_alias
                    )
                )

                if module_file:

                    if self._file_has_function(
                        module_file,
                        function_name
                    ):

                        target = module_file

            # ----------------------------------------------------------
            # Unqualified function call.
            #
            # Only resolve if exactly one repository file defines
            # the function. This avoids ambiguous false dependencies.
            # ----------------------------------------------------------

            else:

                candidates = (
                    functions_by_name.get(
                        simple_name,
                        []
                    )
                )

                # Don't resolve calls to functions defined in the
                # same file as external dependencies.
                candidates = [
                    candidate
                    for candidate in candidates
                    if candidate != file_path
                ]

                if len(candidates) == 1:

                    target = candidates[0]

            if not target:
                continue

            self._add_edge(
                source=file_path,
                target=target,
                edge_type="function_call",
                details={
                    "function": expression,
                    "line": line_number,
                }
            )

    def _file_has_function(
        self,
        file_path: str,
        function_name: str
    ) -> bool:

        return any(
            symbol.get(
                "type"
            ) == "function"
            and symbol.get(
                "name"
            ) == function_name
            for symbol in self.symbols.get(
                file_path,
                []
            )
        )

    # ==================================================================
    # INHERITANCE
    # ==================================================================

    def _extract_inheritance(
        self,
        file_path: str
    ):

        source = self.sources.get(
            file_path,
            ""
        )

        if not source:
            return

        pattern = re.compile(
            r"(?m)^[ \t]*class\s+"
            r"([A-Za-z_]\w*)"
            r"(?:\s*\(([^)]*)\))?"
            r"\s*:"
        )

        for match in pattern.finditer(
            source
        ):

            bases = match.group(
                2
            )

            if not bases:
                continue

            for base in bases.split(
                ","
            ):

                base = base.strip()

                if not base:
                    continue

                simple_base = base.split(
                    "."
                )[-1]

                candidates = []

                for target_file in self.files:

                    for symbol in self.symbols.get(
                        target_file,
                        []
                    ):

                        if (
                            symbol.get(
                                "type"
                            ) == "class"
                            and symbol.get(
                                "name"
                            ) == simple_base
                        ):

                            candidates.append(
                                target_file
                            )

                if len(candidates) != 1:
                    continue

                target = candidates[0]

                if target == file_path:
                    continue

                self._add_edge(
                    source=file_path,
                    target=target,
                    edge_type="inheritance",
                    details={
                        "class": match.group(
                            1
                        ),
                        "base": base,
                        "line": (
                            source.count(
                                "\n",
                                0,
                                match.start()
                            )
                            + 1
                        ),
                    }
                )

    # ==================================================================
    # EDGE MANAGEMENT
    # ==================================================================

    def _add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        details: Optional[
            Dict[str, Any]
        ] = None
    ):

        if not source or not target:
            return

        if source == target:
            return

        edge = self._graph[
            source
        ].setdefault(
            target,
            {
                "types": [],
                "details": [],
            }
        )

        if edge_type not in edge[
            "types"
        ]:

            edge[
                "types"
            ].append(
                edge_type
            )

        if details is not None:

            if details not in edge[
                "details"
            ]:

                edge[
                    "details"
                ].append(
                    details
                )

    def _edges_for_source(
        self,
        source: str
    ) -> List[Dict[str, Any]]:

        result = []

        for target, metadata in (
            self._graph.get(
                source,
                {}
            ).items()
        ):

            for edge_type in metadata.get(
                "types",
                []
            ):

                matching_details = [
                    detail
                    for detail in metadata.get(
                        "details",
                        []
                    )
                    if self._detail_matches_type(
                        detail,
                        edge_type
                    )
                ]

                if matching_details:

                    for detail in matching_details:

                        result.append(
                            {
                                "source": source,
                                "target": target,
                                "type": edge_type,
                                "details": detail,
                            }
                        )

                else:

                    result.append(
                        {
                            "source": source,
                            "target": target,
                            "type": edge_type,
                            "details": {},
                        }
                    )

        return result

    def _detail_matches_type(
        self,
        detail: Dict[str, Any],
        edge_type: str
    ) -> bool:

        if edge_type == "from_import":
            return (
                "module" in detail
                and "name" in detail
            )

        if edge_type == "import":
            return (
                "module" in detail
                and "name" not in detail
            )

        if edge_type == "function_call":
            return (
                "function" in detail
            )

        if edge_type == "inheritance":
            return (
                "base" in detail
            )

        return False

    # ==================================================================
    # REVERSE GRAPH
    # ==================================================================

    def _build_reverse_graph(self):

        self._reverse_graph = defaultdict(
            dict
        )

        for source in self._graph:

            for target, metadata in (
                self._graph[
                    source
                ].items()
            ):

                self._reverse_graph[
                    target
                ][
                    source
                ] = metadata

    # ==================================================================
    # FLAT EDGES
    # ==================================================================

    def _build_edges(
        self
    ) -> List[Dict[str, Any]]:

        result = []

        for source in sorted(
            self._graph.keys()
        ):

            result.extend(
                self._edges_for_source(
                    source
                )
            )

        return result

    # ==================================================================
    # PUBLIC GRAPH
    # ==================================================================

    def _build_public_graph(
        self,
        edges: List[Dict[str, Any]]
    ) -> Dict[
        str,
        List[Dict[str, Any]]
    ]:

        graph = {
            file_path: []
            for file_path in self.files
        }

        for edge in edges:

            graph[
                edge["source"]
            ].append(
                edge
            )

        return graph

    def _build_public_reverse_graph(
        self
    ) -> Dict[
        str,
        List[Dict[str, Any]]
    ]:

        result = {}

        for target, sources in (
            self._reverse_graph.items()
        ):

            result[target] = []

            for source, metadata in (
                sources.items()
            ):

                for edge_type in metadata.get(
                    "types",
                    []
                ):

                    matching_details = [
                        detail
                        for detail in metadata.get(
                            "details",
                            []
                        )
                        if self._detail_matches_type(
                            detail,
                            edge_type
                        )
                    ]

                    if matching_details:

                        for detail in matching_details:

                            result[
                                target
                            ].append(
                                {
                                    "source": source,
                                    "target": target,
                                    "type": edge_type,
                                    "details": detail,
                                }
                            )

                    else:

                        result[
                            target
                        ].append(
                            {
                                "source": source,
                                "target": target,
                                "type": edge_type,
                                "details": {},
                            }
                        )

        for file_path in self.files:

            result.setdefault(
                file_path,
                []
            )

        return result

    # ==================================================================
    # SERIALIZED GRAPH
    # ==================================================================

    def _serialize_dependency_graph(
        self
    ) -> Dict[str, Any]:

        result = {}

        for source in sorted(
            self._graph.keys()
        ):

            result[source] = {}

            for target in sorted(
                self._graph[
                    source
                ].keys()
            ):

                result[source][target] = (
                    self._graph[
                        source
                    ][target]
                )

        return result

    # ==================================================================
    # FILE METADATA
    # ==================================================================

    def _build_file_metadata(
        self
    ) -> Dict[str, Any]:

        result = {}

        for file_path in self.files:

            source = self.sources.get(
                file_path,
                ""
            )

            version = self._detect_version(
                source
            )

            reasons = self._migration_reasons(
                source
            )

            result[file_path] = {
                "file": file_path,
                "module": self._module_name(
                    file_path
                ),
                "version": version,
                "migration_reasons": reasons,
                "functions": [
                    symbol
                    for symbol in self.symbols.get(
                        file_path,
                        []
                    )
                    if symbol.get(
                        "type"
                    ) == "function"
                ],
                "classes": [
                    symbol
                    for symbol in self.symbols.get(
                        file_path,
                        []
                    )
                    if symbol.get(
                        "type"
                    ) == "class"
                ],
                "imports": list(
                    self.imports.get(
                        file_path,
                        []
                    )
                ),
                "from_imports": list(
                    self.from_imports.get(
                        file_path,
                        []
                    )
                ),
                "is_test": self._is_test_file(
                    file_path
                ),
            }

        return result

    # ==================================================================
    # VERSION / MIGRATION REASONS
    # ==================================================================

    def _detect_version(
        self,
        source: str
    ) -> str:

        py2_score = 0
        py3_score = 0

        for pattern in self.PYTHON2_PATTERNS.values():

            if pattern.search(source):
                py2_score += 1

        for pattern in self.PYTHON3_PATTERNS.values():

            if pattern.search(source):
                py3_score += 1

        if py2_score > py3_score and py2_score > 0:
            return "Python 2"

        if py3_score > py2_score and py3_score > 0:
            return "Python 3"

        return "Ambiguous"

    def _migration_reasons(
        self,
        source: str
    ) -> List[str]:

        reasons = []

        for name, pattern in (
            self.PYTHON2_PATTERNS.items()
        ):

            if pattern.search(source):

                reasons.append(
                    name
                )

        return sorted(
            reasons
        )

    # ==================================================================
    # STATISTICS
    # ==================================================================

    def _build_statistics(
        self,
        edges: List[Dict[str, Any]]
    ) -> Dict[str, int]:

        counts = {
            "python_files": len(
                self.files
            ),
            "dependency_edges": len(
                edges
            ),
            "import_edges": 0,
            "from_import_edges": 0,
            "function_call_edges": 0,
            "inheritance_edges": 0,
        }

        for edge in edges:

            edge_type = edge.get(
                "type"
            )

            if edge_type == "import":
                counts[
                    "import_edges"
                ] += 1

            elif edge_type == "from_import":
                counts[
                    "from_import_edges"
                ] += 1

            elif edge_type == "function_call":
                counts[
                    "function_call_edges"
                ] += 1

            elif edge_type == "inheritance":
                counts[
                    "inheritance_edges"
                ] += 1

        return counts

    # ==================================================================
    # HELPERS
    # ==================================================================

    @staticmethod
    def _node_name(
        node
    ) -> Optional[str]:

        name = getattr(
            node,
            "name",
            None
        )

        if name is not None:

            value = getattr(
                name,
                "value",
                None
            )

            if value:
                return value

        value = getattr(
            node,
            "value",
            None
        )

        return value

    @staticmethod
    def _line(
        node
    ) -> Optional[int]:

        try:
            return node.start_pos[0]

        except Exception:
            return None

    @staticmethod
    def _is_test_file(
        file_path: str
    ) -> bool:

        normalized = file_path.lower()

        filename = Path(
            normalized
        ).name

        return (
            filename.startswith("test_")
            or filename.endswith("_test.py")
            or normalized.startswith("tests/")
            or "/tests/" in normalized
        )

    # ==================================================================
    # SAVE
    # ==================================================================

    def save(
        self,
        output_path: str
    ) -> Dict[str, Any]:

        result = self.analyze()

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
                result,
                f,
                indent=2,
                ensure_ascii=False
            )

        return result