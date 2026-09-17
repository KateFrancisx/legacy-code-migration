from __future__ import annotations

from typing import Any, Dict, Optional

from .base import (
    MigrationLLM,
    MigrationResult,
)


class MigrationService:
    """
    Model-independent migration service.

    The caller does not need to know whether
    Gemini, Qwen, GPT, or Claude is being used.
    """

    def __init__(
        self,
        llm: MigrationLLM,
    ):

        self.llm = llm

    def migrate_unit(
        self,
        source_code: str,
        prompt: str,
        repository_context: Optional[
            Dict[str, Any]
        ] = None,
    ) -> MigrationResult:

        return self.llm.migrate(
            source_code=source_code,
            prompt=prompt,
            repository_context=repository_context,
        )