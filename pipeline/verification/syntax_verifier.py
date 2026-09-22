from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class SyntaxVerifier:
    """
    Verifies whether migrated Python source files are
    syntactically valid Python 3 code.
    """

    def verify_file(self, file_path: str | Path) -> dict[str, Any]:
        """
        Verify a single Python file.

        Returns a structured verification result.
        """

        path = Path(file_path)

        result = {
            "file": str(path),
            "syntax_valid": False,
            "error": None,
            "error_type": None,
            "line": None,
            "column": None,
        }

        if not path.exists():
            result["error"] = "File does not exist."
            result["error_type"] = "FileNotFoundError"
            return result

        try:
            source = path.read_text(encoding="utf-8")

            ast.parse(
                source,
                filename=str(path),
                mode="exec",
            )

            result["syntax_valid"] = True

        except SyntaxError as exc:
            result["error"] = exc.msg
            result["error_type"] = "SyntaxError"
            result["line"] = exc.lineno
            result["column"] = exc.offset

        except UnicodeDecodeError as exc:
            result["error"] = str(exc)
            result["error_type"] = "UnicodeDecodeError"

        except Exception as exc:
            result["error"] = str(exc)
            result["error_type"] = type(exc).__name__

        return result

    def verify_directory(self, directory: str | Path) -> dict[str, Any]:
        """
        Verify all Python files in a migrated directory.
        """

        directory = Path(directory)

        results = []

        if not directory.exists():
            return {
                "directory": str(directory),
                "files_checked": 0,
                "valid_files": 0,
                "invalid_files": 0,
                "overall_status": "ERROR",
                "results": [],
                "error": "Directory does not exist.",
            }

        python_files = sorted(directory.rglob("*.py"))

        for file_path in python_files:
            results.append(self.verify_file(file_path))

        valid_files = sum(
            1 for result in results
            if result["syntax_valid"]
        )

        invalid_files = len(results) - valid_files

        if invalid_files == 0:
            overall_status = "PASS"
        else:
            overall_status = "FAIL"

        return {
            "directory": str(directory),
            "files_checked": len(results),
            "valid_files": valid_files,
            "invalid_files": invalid_files,
            "overall_status": overall_status,
            "results": results,
        }