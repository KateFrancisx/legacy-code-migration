from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class MigrationResult:
    """
    Standard result returned by every migration LLM.
    """

    success: bool

    source_code: str

    migrated_code: str = ""

    model: str = ""

    provider: str = ""

    explanation: str = ""

    raw_response: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "source_code": self.source_code,
            "migrated_code": self.migrated_code,
            "model": self.model,
            "provider": self.provider,
            "explanation": self.explanation,
            "raw_response": self.raw_response,
            "metadata": self.metadata,
            "error": self.error,
        }


class MigrationLLM(ABC):
    """
    Common interface for all migration LLM providers.

    Future implementations:

        GeminiMigrator
        QwenMigrator
        OpenAIMigrator
        ClaudeMigrator
    """

    @abstractmethod
    def migrate(
        self,
        source_code: str,
        prompt: str,
        repository_context: Optional[
            Dict[str, Any]
        ] = None,
    ) -> MigrationResult:
        """
        Migrate legacy source code to the target version.
        """
        raise NotImplementedError