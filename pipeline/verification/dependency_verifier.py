from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any


class DependencyVerifier:
    """
    Verifies imports and internal module dependencies
    in a migrated Python repository.
    """

    def _get_imports(self, file_path: Path) -> list[str]:
        """
        Extract imported module names from a Python file.
        """

        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        imports = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])

        return sorted(set(imports))

    def _is_local_module(
        self,
        module_name: str,
        repository_dir: Path,
    ) -> bool:
        """
        Check whether an imported module exists
        inside the migrated repository.
        """

        module_file = repository_dir / f"{module_name}.py"
        package_dir = repository_dir / module_name / "__init__.py"

        return module_file.exists() or package_dir.exists()

    def _is_importable(
        self,
        module_name: str,
        repository_dir: Path,
    ) -> bool:
        """
        Check whether a module can be resolved by Python.
        """

        existing_path = list(sys.path)

        try:
            sys.path.insert(0, str(repository_dir))

            spec = importlib.util.find_spec(module_name)

            return spec is not None

        except (ImportError, ModuleNotFoundError, ValueError):
            return False

        finally:
            sys.path.clear()
            sys.path.extend(existing_path)

    def verify_file(
        self,
        file_path: str | Path,
        repository_dir: str | Path,
    ) -> dict[str, Any]:
        """
        Verify imports for a single migrated Python file.
        """

        file_path = Path(file_path)
        repository_dir = Path(repository_dir)

        result = {
            "file": str(file_path),
            "imports": [],
            "local_dependencies": [],
            "missing_local_dependencies": [],
            "unresolved_imports": [],
            "dependency_valid": False,
            "error": None,
        }

        try:
            imports = self._get_imports(file_path)

            result["imports"] = imports

            for module_name in imports:

                if self._is_local_module(
                    module_name,
                    repository_dir,
                ):
                    result["local_dependencies"].append(
                        module_name
                    )

                    if not self._is_importable(
                        module_name,
                        repository_dir,
                    ):
                        result["unresolved_imports"].append(
                            module_name
                        )

                else:
                    # Not a local module.
                    # It may be a standard library or installed package.
                    if not self._is_importable(
                        module_name,
                        repository_dir,
                    ):
                        result["unresolved_imports"].append(
                            module_name
                        )

            result["missing_local_dependencies"] = [
                module
                for module in imports
                if not self._is_local_module(
                    module,
                    repository_dir,
                )
                and module not in {
                    "os",
                    "sys",
                    "json",
                    "math",
                    "typing",
                    "pathlib",
                    "re",
                    "datetime",
                    "time",
                    "collections",
                    "itertools",
                    "functools",
                    "logging",
                    "subprocess",
                    "random",
                }
            ]

            result["dependency_valid"] = (
                len(result["unresolved_imports"]) == 0
            )

        except Exception as exc:
            result["error"] = str(exc)
            result["dependency_valid"] = False

        return result

    def verify_directory(
        self,
        repository_dir: str | Path,
    ) -> dict[str, Any]:
        """
        Verify imports for all migrated Python files.
        """

        repository_dir = Path(repository_dir)

        if not repository_dir.exists():
            return {
                "directory": str(repository_dir),
                "files_checked": 0,
                "valid_files": 0,
                "invalid_files": 0,
                "overall_status": "ERROR",
                "results": [],
                "error": "Directory does not exist.",
            }

        python_files = sorted(
            repository_dir.rglob("*.py")
        )

        results = []

        for file_path in python_files:
            results.append(
                self.verify_file(
                    file_path,
                    repository_dir,
                )
            )

        valid_files = sum(
            1
            for result in results
            if result["dependency_valid"]
        )

        invalid_files = (
            len(results) - valid_files
        )

        overall_status = (
            "PASS"
            if invalid_files == 0
            else "FAIL"
        )

        return {
            "directory": str(repository_dir),
            "files_checked": len(results),
            "valid_files": valid_files,
            "invalid_files": invalid_files,
            "overall_status": overall_status,
            "results": results,
        }