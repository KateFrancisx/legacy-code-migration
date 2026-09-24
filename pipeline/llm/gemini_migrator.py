from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from google import genai

from .base import (
    MigrationLLM,
    MigrationResult,
)


load_dotenv()


class GeminiMigrator(MigrationLLM):
    """
    Gemini-backed legacy code migration engine.

    The rest of the migration pipeline does not need
    to know that Gemini is being used.
    """

    DEFAULT_MODEL = "gemini-3.6-flash"

    # Retry configuration
    MAX_RETRIES = 4
    INITIAL_RETRY_DELAY = 2

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):

        self.model = (
            model
            or os.getenv("GEMINI_MODEL")
            or self.DEFAULT_MODEL
        )

        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
        )

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. "
                "Add it to your .env file."
            )

        self.client = genai.Client(
            api_key=self.api_key
        )

    # =====================================================
    # Migration
    # =====================================================

    def migrate(
        self,
        source_code: str,
        prompt: str,
        repository_context: Optional[
            Dict[str, Any]
        ] = None,
    ) -> MigrationResult:

        if not source_code.strip():
            return MigrationResult(
                success=False,
                source_code=source_code,
                provider="Gemini",
                model=self.model,
                error="Source code is empty.",
            )

        last_error = None

        for attempt in range(
            1,
            self.MAX_RETRIES + 1,
        ):

            try:

                print(
                    f"  [Gemini] Attempt "
                    f"{attempt}/{self.MAX_RETRIES}"
                )

                response = (
                    self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                    )
                )

                raw_text = (
                    getattr(
                        response,
                        "text",
                        None,
                    )
                    or ""
                )

                migrated_code = (
                    self._extract_code(
                        raw_text
                    )
                )

                explanation = (
                    self._extract_explanation(
                        raw_text
                    )
                )

                return MigrationResult(
                    success=bool(
                        migrated_code.strip()
                    ),
                    source_code=source_code,
                    migrated_code=migrated_code,
                    provider="Gemini",
                    model=self.model,
                    explanation=explanation,
                    raw_response=raw_text,
                    metadata={
                        "repository_context_provided":
                            repository_context
                            is not None,
                        "attempts": attempt,
                    },
                )

            except Exception as exc:

                last_error = exc
                error_text = str(exc)

                # Temporary Gemini/API availability errors
                retryable = (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text
                    or "429" in error_text
                    or "RESOURCE_EXHAUSTED"
                    in error_text
                    or "500" in error_text
                    or "INTERNAL"
                    in error_text
                )

                if (
                    retryable
                    and attempt < self.MAX_RETRIES
                ):

                    delay = (
                        self.INITIAL_RETRY_DELAY
                        * (2 ** (attempt - 1))
                    )

                    print(
                        f"  [Gemini] Temporary API error: "
                        f"{error_text}"
                    )

                    print(
                        f"  [Gemini] Retrying in "
                        f"{delay} seconds..."
                    )

                    time.sleep(delay)

                    continue

                # Non-retryable error, or all retries exhausted
                break

        return MigrationResult(
            success=False,
            source_code=source_code,
            provider="Gemini",
            model=self.model,
            error=str(last_error),
        )

    # =====================================================
    # Code extraction
    # =====================================================

    @staticmethod
    def _extract_code(
        response_text: str,
    ) -> str:

        text = response_text.strip()

        if not text:
            return ""

        # Preferred format:
        #
        # ```python
        # migrated code
        # ```

        if "```python" in text:

            start = (
                text.find(
                    "```python"
                )
                + len("```python")
            )

            end = text.find(
                "```",
                start,
            )

            if end != -1:
                return text[
                    start:end
                ].strip()

        # Generic fenced block.

        if "```" in text:

            parts = text.split("```")

            if len(parts) >= 3:

                code = parts[1]

                if code.startswith(
                    "python"
                ):
                    code = code[
                        len("python"):
                    ]

                return code.strip()

        # If no fence exists, return the full
        # response. The prompt should request
        # code-only output.

        return text

    # =====================================================
    # Explanation extraction
    # =====================================================

    @staticmethod
    def _extract_explanation(
        response_text: str,
    ) -> str:

        text = response_text.strip()

        if not text:
            return ""

        # If fenced Python exists, everything outside
        # the code fence is considered explanation.

        if "```" in text:

            parts = text.split("```")

            if len(parts) >= 3:

                explanation_parts = []

                for index, part in enumerate(
                    parts
                ):

                    if index % 2 == 0:
                        if part.strip():
                            explanation_parts.append(
                                part.strip()
                            )

                return "\n".join(
                    explanation_parts
                ).strip()

        return ""