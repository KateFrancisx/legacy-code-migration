from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List


class RepositoryAssembler:
    """
    Builds the final migrated repository from:

    1. Original repository
    2. Migration plan
    3. LLM-generated migrated files

    Decisions are controlled by the migration plan:

        MIGRATE  -> use LLM-generated file
        PRESERVE -> copy original file unchanged
        SKIP     -> do not include in production migrated repo

    Non-Python repository files that are not explicitly part of
    MIGRATE/SKIP are automatically preserved.
    """

    def __init__(
        self,
        original_repo: str | Path,
        migration_plan: Dict[str, Any],
        llm_output_dir: str | Path,
        output_dir: str | Path,
    ) -> None:

        self.original_repo = Path(
            original_repo
        ).resolve()

        self.migration_plan = migration_plan

        self.llm_output_dir = Path(
            llm_output_dir
        ).resolve()

        self.output_dir = Path(
            output_dir
        ).resolve()

        if not self.original_repo.exists():
            raise FileNotFoundError(
                f"Original repository does not exist: "
                f"{self.original_repo}"
            )

        if not self.original_repo.is_dir():
            raise NotADirectoryError(
                f"Original repository is not a directory: "
                f"{self.original_repo}"
            )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ============================================================
    # NORMALIZATION
    # ============================================================

    @staticmethod
    def _normalize_path(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        path = str(value)

        path = path.replace("\\", "/")

        # Remove accidental leading "./"
        while path.startswith("./"):
            path = path[2:]

        # Remove accidental leading slash
        path = path.lstrip("/")

        return path

    # ============================================================
    # PLAN EXTRACTION
    # ============================================================

    def _get_migration_files(self) -> List[str]:
        """
        Extract files that must be migrated.
        """

        migrate = (
            self.migration_plan.get("migrate")
            or []
        )

        result = []

        if not isinstance(migrate, list):
            return result

        for item in migrate:

            if isinstance(item, str):
                path = item

            elif isinstance(item, dict):
                path = (
                    item.get("file")
                    or item.get("path")
                    or item.get("file_path")
                    or ""
                )

            else:
                continue

            path = self._normalize_path(path)

            if path:
                result.append(path)

        return result

    def _get_preserve_files(self) -> List[str]:
        """
        Extract files that must be preserved unchanged.
        """

        preserve = (
            self.migration_plan.get("preserve")
            or []
        )

        result = []

        if not isinstance(preserve, list):
            return result

        for item in preserve:

            if isinstance(item, str):
                path = item

            elif isinstance(item, dict):
                path = (
                    item.get("file")
                    or item.get("path")
                    or item.get("file_path")
                    or ""
                )

            else:
                continue

            path = self._normalize_path(path)

            if path:
                result.append(path)

        return result

    def _get_skip_files(self) -> List[str]:
        """
        Extract files that should not be placed in the
        production migrated repository.
        """

        skip = (
            self.migration_plan.get("skip")
            or []
        )

        result = []

        if not isinstance(skip, list):
            return result

        for item in skip:

            if isinstance(item, str):
                path = item

            elif isinstance(item, dict):
                path = (
                    item.get("file")
                    or item.get("path")
                    or item.get("file_path")
                    or ""
                )

            else:
                continue

            path = self._normalize_path(path)

            if path:
                result.append(path)

        return result

    # ============================================================
    # FILE OPERATIONS
    # ============================================================

    def _copy_file(
        self,
        relative_path: str,
        destination_path: Path | None = None,
    ) -> None:

        relative_path = self._normalize_path(
            relative_path
        )

        source = (
            self.original_repo
            / Path(relative_path)
        )

        if destination_path is None:
            destination = (
                self.output_dir
                / Path(relative_path)
            )
        else:
            destination = destination_path

        if not source.exists():
            raise FileNotFoundError(
                f"Original file does not exist: "
                f"{source}"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    def _copy_llm_file(
        self,
        relative_path: str,
    ) -> Path:

        relative_path = self._normalize_path(
            relative_path
        )

        source = (
            self.llm_output_dir
            / Path(relative_path)
        )

        destination = (
            self.output_dir
            / Path(relative_path)
        )

        if not source.exists():
            raise FileNotFoundError(
                f"LLM-generated file does not exist: "
                f"{source}"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

        return destination

    # ============================================================
    # ALL ORIGINAL FILES
    # ============================================================

    def _get_all_repository_files(self) -> List[str]:
        """
        Return all files in the original repository.

        This intentionally includes non-Python files such as:

            README.md
            requirements.txt
            .gitignore
            JSON files
            JavaScript files
            configuration files
            frontend files
            etc.
        """

        result = []

        for path in self.original_repo.rglob("*"):

            if not path.is_file():
                continue

            relative = path.relative_to(
                self.original_repo
            )

            # Ignore common local/environment directories.
            parts = {
                part.lower()
                for part in relative.parts
            }

            ignored_dirs = {
                ".git",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".venv",
                "venv",
            }

            if parts.intersection(
                ignored_dirs
            ):
                continue

            result.append(
                self._normalize_path(
                    relative.as_posix()
                )
            )

        return sorted(result)

    # ============================================================
    # ASSEMBLY
    # ============================================================

    def assemble(self) -> Dict[str, Any]:
        """
        Build the complete migrated repository.

        Returns an assembly manifest describing exactly what
        happened to every file.
        """

        migrate_files = set(
            self._get_migration_files()
        )

        preserve_files = set(
            self._get_preserve_files()
        )

        skip_files = set(
            self._get_skip_files()
        )

        # MIGRATE always has priority.
        preserve_files -= migrate_files
        skip_files -= migrate_files

        # PRESERVE has priority over SKIP.
        skip_files -= preserve_files

        all_files = self._get_all_repository_files()

        manifest = {
            "original_repository": str(
                self.original_repo
            ),
            "output_repository": str(
                self.output_dir
            ),
            "files": [],
            "statistics": {
                "original_files": len(
                    all_files
                ),
                "migrated_files": 0,
                "preserved_files": 0,
                "skipped_files": 0,
                "automatically_preserved_files": 0,
                "errors": 0,
            },
        }

        # ========================================================
        # PROCESS EVERY ORIGINAL FILE
        # ========================================================

        for relative_path in all_files:

            # ----------------------------------------------------
            # MIGRATE
            # ----------------------------------------------------

            if relative_path in migrate_files:

                try:
                    destination = (
                        self._copy_llm_file(
                            relative_path
                        )
                    )

                    manifest["files"].append(
                        {
                            "file": relative_path,
                            "decision": "MIGRATE",
                            "source": "LLM",
                            "destination": str(
                                destination
                            ),
                            "status": "SUCCESS",
                        }
                    )

                    manifest["statistics"][
                        "migrated_files"
                    ] += 1

                except Exception as exc:

                    manifest["files"].append(
                        {
                            "file": relative_path,
                            "decision": "MIGRATE",
                            "source": "LLM",
                            "status": "FAILED",
                            "error": str(exc),
                        }
                    )

                    manifest["statistics"][
                        "errors"
                    ] += 1

                continue

            # ----------------------------------------------------
            # PRESERVE
            # ----------------------------------------------------

            if relative_path in preserve_files:

                try:
                    self._copy_file(
                        relative_path
                    )

                    manifest["files"].append(
                        {
                            "file": relative_path,
                            "decision": "PRESERVE",
                            "source": "ORIGINAL",
                            "status": "SUCCESS",
                        }
                    )

                    manifest["statistics"][
                        "preserved_files"
                    ] += 1

                except Exception as exc:

                    manifest["files"].append(
                        {
                            "file": relative_path,
                            "decision": "PRESERVE",
                            "source": "ORIGINAL",
                            "status": "FAILED",
                            "error": str(exc),
                        }
                    )

                    manifest["statistics"][
                        "errors"
                    ] += 1

                continue

            # ----------------------------------------------------
            # SKIP
            # ----------------------------------------------------

            if relative_path in skip_files:

                manifest["files"].append(
                    {
                        "file": relative_path,
                        "decision": "SKIP",
                        "source": "ORIGINAL",
                        "status": "SKIPPED",
                    }
                )

                manifest["statistics"][
                    "skipped_files"
                ] += 1

                continue

            # ----------------------------------------------------
            # AUTOMATIC PRESERVE
            #
            # Any repository file that isn't a migration target
            # or explicit skip is preserved.
            #
            # This is what keeps:
            #
            #   requirements.txt
            #   README.md
            #   .gitignore
            #   frontend/
            #   data/
            #
            # in the final repository.
            # ----------------------------------------------------

            try:
                self._copy_file(
                    relative_path
                )

                manifest["files"].append(
                    {
                        "file": relative_path,
                        "decision": "PRESERVE",
                        "source": "ORIGINAL",
                        "reason": "AUTOMATIC_NON_MIGRATED_FILE",
                        "status": "SUCCESS",
                    }
                )

                manifest["statistics"][
                    "preserved_files"
                ] += 1

                manifest["statistics"][
                    "automatically_preserved_files"
                ] += 1

            except Exception as exc:

                manifest["files"].append(
                    {
                        "file": relative_path,
                        "decision": "PRESERVE",
                        "source": "ORIGINAL",
                        "reason": "AUTOMATIC_NON_MIGRATED_FILE",
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )

                manifest["statistics"][
                    "errors"
                ] += 1

        # ========================================================
        # CHECK FOR LLM FILES THAT WERE EXPECTED BUT MISSING
        # ========================================================

        processed_migrate_files = {
            item["file"]
            for item in manifest["files"]
            if (
                item.get("decision") == "MIGRATE"
                and item.get("status") == "SUCCESS"
            )
        }

        missing_llm_outputs = sorted(
            migrate_files
            - processed_migrate_files
        )

        manifest[
            "missing_llm_outputs"
        ] = missing_llm_outputs

        # ========================================================
        # FINAL STATUS
        # ========================================================

        if (
            manifest["statistics"]["errors"] > 0
            or missing_llm_outputs
        ):
            manifest["status"] = "FAILED"

        else:
            manifest["status"] = "SUCCESS"

        return manifest