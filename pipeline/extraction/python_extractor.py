#!/usr/bin/env python3
"""
Python Function Extractor — Module 3 (repo mapping context) + Module 4
(static analysis) combined, scoped to Python only.

Takes target files from migration_job_selector's output, parses each with
parso (grammar 2.7, since these are Python 2 source files), and splits
them into individual FunctionRecord objects — one per function/method.

Feature set extracted per function (matches the migration_examples DB
columns imports_original / classes / functions / static_analysis):
  - exact source slice, line range, params
  - file-level imports (context for that function)
  - enclosing class name + base classes (if it's a method)
  - names of functions/methods called inside the body (call-graph prep)
  - basic metrics: LOC, branch count, param count

Usage:
    python python_extractor.py migration_job.json --repo-root <path> -o functions.json
"""

import argparse
import json
from pathlib import Path
from typing import Optional

import parso

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import FunctionRecord, FunctionExtractor


class PythonExtractor(FunctionExtractor):
    language = "Python"

    def extract(self, file_path: str, source: str, language_version: str) -> list:
        grammar = parso.load_grammar(version="2.7" if language_version == "2" else "3.10")
        try:
            tree = grammar.parse(source)
        except Exception as e:
            print(f"  [WARN] failed to parse {file_path}: {e}")
            return []

        imports = self._extract_imports(tree)
        records = []
        self._walk(tree, file_path, source, imports, language_version,
                   enclosing_class=None, records=records)
        return records

    # ---- helpers -----------------------------------------------------

    def _extract_imports(self, tree) -> list:
        """Collect all import statements at any level of the file, as
        plain text (e.g. 'import urllib2', 'from foo import bar')."""
        imports = []
        for node in self._iter_all(tree):
            if node.type in ("import_name", "import_from"):
                try:
                    imports.append(node.get_code().strip())
                except Exception:
                    pass
        return imports

    def _iter_all(self, node):
        yield node
        if hasattr(node, "children"):
            for child in node.children:
                yield from self._iter_all(child)

    def _walk(self, node, file_path, full_source, imports, language_version,
              enclosing_class, records):
        """Recursively walk the tree, extracting funcdefs and classdefs."""
        for child in node.children if hasattr(node, "children") else []:
            if child.type == "classdef":
                class_name = child.name.value
                bases = self._extract_bases(child)
                class_info = {"name": class_name, "bases": bases}
                self._walk(child, file_path, full_source, imports, language_version,
                           enclosing_class=class_info, records=records)

            elif child.type == "funcdef":
                record = self._build_record(child, file_path, full_source, imports,
                                             language_version, enclosing_class)
                records.append(record)
                # walk inside for nested functions too
                self._walk(child, file_path, full_source, imports, language_version,
                           enclosing_class=enclosing_class, records=records)
            else:
                self._walk(child, file_path, full_source, imports, language_version,
                           enclosing_class=enclosing_class, records=records)

    def _extract_bases(self, classdef_node) -> list:
        bases = []
        try:
            arglist = classdef_node.children[3] if len(classdef_node.children) > 3 else None
            if arglist is not None and arglist.type not in ("operator",):
                bases = [leaf.value for leaf in self._iter_all(arglist) if leaf.type == "name"]
        except Exception:
            pass
        return bases

    def _build_record(self, funcdef_node, file_path, full_source, imports,
                       language_version, enclosing_class) -> FunctionRecord:
        name = funcdef_node.name.value
        qualified_name = f"{enclosing_class['name']}.{name}" if enclosing_class else name

        start_line = funcdef_node.start_pos[0]
        end_line = funcdef_node.end_pos[0]
        chunk_id = f"{file_path}::{qualified_name}::L{start_line}-L{end_line}"

        source_lines = full_source.splitlines()
        source_slice = "\n".join(source_lines[start_line - 1:end_line])

        params = self._extract_params(funcdef_node)
        calls = self._extract_calls(funcdef_node)
        metrics = self._compute_metrics(funcdef_node, source_slice, params)

        return FunctionRecord(
            chunk_id=chunk_id,
            chunk_type="function",
            function_name=name,
            function_full_name=qualified_name,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            original_code=source_slice,
            params=params,
            imports_original=imports,
            classes=enclosing_class,
            functions=calls,
            static_analysis=metrics,
            source_language="Python",
            language_version=language_version,
        )

    def _extract_params(self, funcdef_node) -> list:
        params = []
        try:
            parameters_node = funcdef_node.children[2]  # parameters node
            for leaf in self._iter_all(parameters_node):
                if leaf.type == "name":
                    params.append(leaf.value)
        except Exception:
            pass
        return params

    def _extract_calls(self, funcdef_node) -> list:
        """Best-effort: find NAME tokens immediately followed by a trailer
        that starts with '(' -> treat as a function/method call."""
        calls = set()
        nodes = list(self._iter_all(funcdef_node))
        for i, n in enumerate(nodes):
            if n.type == "name":
                nxt = nodes[i + 1] if i + 1 < len(nodes) else None
                # crude heuristic: a name followed somewhere shortly by '(' operator
                # sharing the same parent 'power'/'atom_expr' node
                parent = getattr(n, "parent", None)
                if parent is not None and parent.type in ("power", "atom_expr"):
                    siblings = parent.children
                    if len(siblings) > 1 and siblings[0] is n:
                        second = siblings[1]
                        if second.type == "trailer" and second.children and \
                           second.children[0].type == "operator" and second.children[0].value == "(":
                            calls.add(n.value)
        return sorted(calls)

    def _compute_metrics(self, funcdef_node, source_slice, params) -> dict:
        all_nodes = list(self._iter_all(funcdef_node))

        branch_keywords = {"if", "elif", "for", "while", "try", "except"}
        branch_count = sum(1 for n in all_nodes if n.type == "keyword" and n.value in branch_keywords)

        loc = len([l for l in source_slice.splitlines() if l.strip()])

        # nesting depth: how deep compound statements (if/for/while/try) go
        nesting_depth = self._max_nesting_depth(funcdef_node)

        # presence flags -- cheap, useful signals for similarity + risk later
        has_loop = any(n.type in ("for_stmt", "while_stmt") for n in all_nodes)
        has_exception_handling = any(n.type == "try_stmt" for n in all_nodes)
        has_nested_function = sum(1 for n in all_nodes if n.type == "funcdef") - 1  # minus itself
        has_return = any(n.type == "keyword" and n.value == "return" for n in all_nodes)
        has_yield = any(n.type == "keyword" and n.value == "yield" for n in all_nodes)

        # rough node-type histogram, limited to structurally meaningful types
        # (skip leaf-level noise like every single operator/name token)
        interesting_types = {"if_stmt", "for_stmt", "while_stmt", "try_stmt",
                              "funcdef", "classdef", "return_stmt", "with_stmt",
                              "comparison", "power", "atom_expr"}
        node_type_counts = {}
        for n in all_nodes:
            if n.type in interesting_types:
                node_type_counts[n.type] = node_type_counts.get(n.type, 0) + 1

        return {
            "loc": loc,
            "branch_count": branch_count,
            "param_count": len(params),
            "cyclomatic_complexity": branch_count + 1,
            "nesting_depth": nesting_depth,
            "has_loop": has_loop,
            "has_exception_handling": has_exception_handling,
            "nested_function_count": max(has_nested_function, 0),
            "has_return": has_return,
            "has_yield": has_yield,
            "node_type_counts": node_type_counts,
        }

    def _max_nesting_depth(self, node, current_depth=0) -> int:
        compound_types = {"if_stmt", "for_stmt", "while_stmt", "try_stmt", "with_stmt"}
        max_depth = current_depth
        for child in getattr(node, "children", []):
            child_depth = current_depth + 1 if child.type in compound_types else current_depth
            max_depth = max(max_depth, self._max_nesting_depth(child, child_depth))
        return max_depth


def load_target_files(job_path: str, repo_root: str) -> list:
    with open(job_path) as f:
        job = json.load(f)
    return job["targets"]


def main():
    parser = argparse.ArgumentParser(description="Extract functions from migration job target files")
    parser.add_argument("job_path", help="Path to migration_job.json from migration_job_selector.py")
    parser.add_argument("--repo-root", required=True, help="Repo root the manifest paths are relative to")
    parser.add_argument("-o", "--output", default="functions.json")
    args = parser.parse_args()

    targets = load_target_files(args.job_path, args.repo_root)
    extractor = PythonExtractor()
    repo_root = Path(args.repo_root)

    all_records = []
    for entry in targets:
        file_path = repo_root / entry["path"]
        try:
            source = file_path.read_text(errors="ignore")
        except OSError as e:
            print(f"  [WARN] could not read {file_path}: {e}")
            continue

        language_version = entry.get("version_detection", {}).get("version", "2")
        records = extractor.extract(entry["path"], source, language_version)
        all_records.extend(records)
        print(f"  {entry['path']}: {len(records)} functions extracted")

    with open(args.output, "w") as f:
        json.dump([r.to_dict() for r in all_records], f, indent=2)

    print(f"\nTotal functions extracted: {len(all_records)}")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()