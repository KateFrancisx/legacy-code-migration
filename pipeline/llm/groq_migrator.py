from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from groq import Groq

from .base import (
    MigrationLLM,
    MigrationResult,
)


load_dotenv()


class GroqMigrator(MigrationLLM):
    """
    Groq-backed legacy code migration engine.

    Uses the same MigrationLLM interface as GeminiMigrator,
    so the rest of the CodeMigrate pipeline remains unchanged.
    """

    DEFAULT_MODEL = "openai/gpt-oss-120b"

    # Keep comfortably below the current 8,000 TPM limit.
    # The exact token count depends on the tokenizer, so we
    # intentionally target a lower limit.
    TARGET_PROMPT_CHARS = 26000

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):

        self.model = (
            model
            or os.getenv("GROQ_MODEL")
            or self.DEFAULT_MODEL
        )

        self.api_key = (
            api_key
            or os.getenv("GROQ_API_KEY")
        )

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured. "
                "Add it to your .env file."
            )

        self.client = Groq(
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
                provider="Groq",
                model=self.model,
                error="Source code is empty.",
            )

        # Reduce oversized RAG prompts before sending them.
        final_prompt = self._prepare_prompt(
            prompt=prompt,
            source_code=source_code,
        )

        prompt_chars = len(final_prompt)

        print(
            f"  [Groq] Prompt size: "
            f"{prompt_chars:,} characters"
        )

        try:

            response = (
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": final_prompt,
                        }
                    ],
                    temperature=0.1,
                )
            )

            raw_text = (
                response.choices[0]
                .message
                .content
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
                provider="Groq",
                model=self.model,
                explanation=explanation,
                raw_response=raw_text,
                metadata={
                    "repository_context_provided":
                        repository_context
                        is not None,
                    "prompt_characters":
                        prompt_chars,
                    "prompt_trimmed":
                        prompt_chars
                        < len(prompt),
                },
            )

        except Exception as exc:

            return MigrationResult(
                success=False,
                source_code=source_code,
                provider="Groq",
                model=self.model,
                error=str(exc),
                metadata={
                    "prompt_characters":
                        prompt_chars,
                },
            )

    # =====================================================
    # Prompt preparation
    # =====================================================

    @classmethod
    def _prepare_prompt(
        cls,
        prompt: str,
        source_code: str,
    ) -> str:

        if len(prompt) <= cls.TARGET_PROMPT_CHARS:
            return prompt

        print(
            f"  [Groq] Prompt is large "
            f"({len(prompt):,} chars)."
        )

        print(
            f"  [Groq] Reducing RAG context "
            f"to fit model limits..."
        )

        # Try to identify common RAG/context sections.
        markers = [
            "Historical migration examples",
            "RAG",
            "Retrieved examples",
            "retrieved examples",
            "Migration examples",
            "Examples from previous migrations",
        ]

        marker_position = -1

        for marker in markers:

            position = prompt.find(marker)

            if position != -1:

                marker_position = position

                break

        if marker_position != -1:

            # Preserve everything before the examples.
            prefix = prompt[:marker_position]

            remaining = (
                cls.TARGET_PROMPT_CHARS
                - len(prefix)
            )

            if remaining > 0:

                rag_context = prompt[
                    marker_position:
                ]

                rag_context = (
                    cls._trim_rag_context(
                        rag_context,
                        remaining,
                    )
                )

                result = (
                    prefix
                    + rag_context
                )

                # Always reinforce the output requirement.
                result += (
                    "\n\nIMPORTANT:\n"
                    "Return the complete migrated "
                    "Python 3 source code.\n"
                    "Do not omit functions or classes.\n"
                    "Do not provide partial code.\n"
                )

                return result

        # Fallback:
        # Preserve the beginning and the original source code.
        #
        # This is safer than blindly cutting the end because
        # migration instructions are normally near the beginning.
        source_marker = prompt.find(
            source_code
        )

        if source_marker != -1:

            prefix = prompt[:source_marker]

            suffix = prompt[
                source_marker:
                source_marker
                + len(source_code)
            ]

            available = (
                cls.TARGET_PROMPT_CHARS
                - len(prefix)
                - len(suffix)
            )

            if available < 0:

                # Extremely large source file.
                suffix = source_code[
                    :max(
                        1000,
                        cls.TARGET_PROMPT_CHARS
                        - len(prefix),
                    )
                ]

            result = (
                prefix
                + "\n\nSOURCE CODE:\n"
                + suffix
                + "\n\n"
                "Return the complete migrated "
                "Python 3 source code."
            )

            return result

        # Final fallback.
        return (
            prompt[
                :cls.TARGET_PROMPT_CHARS
            ]
            + "\n\n"
            "IMPORTANT:\n"
            "Return the complete migrated "
            "Python 3 source code."
        )

    @staticmethod
    def _trim_rag_context(
        text: str,
        max_chars: int,
    ) -> str:

        if len(text) <= max_chars:
            return text

        # Prefer keeping complete example blocks.
        #
        # Common separators used by RAG prompt generators.
        separators = [
            "\n\n",
            "\n---\n",
            "\n###",
        ]

        chunks = [text]

        for separator in separators:

            if separator in text:

                chunks = text.split(
                    separator
                )

                if len(chunks) > 1:
                    break

        result_parts = []
        current_size = 0

        for chunk in chunks:

            addition = (
                chunk
                if not result_parts
                else "\n\n" + chunk
            )

            if (
                current_size
                + len(addition)
                > max_chars
            ):
                break

            result_parts.append(
                addition
            )

            current_size += len(addition)

        result = "".join(
            result_parts
        ).strip()

        return result

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

        # ```python
        # ...
        # ```

        python_fence = re.search(
            r"```python\s*(.*?)```",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        if python_fence:

            return python_fence.group(
                1
            ).strip()

        # Generic code fence.

        generic_fence = re.search(
            r"```\s*(.*?)```",
            text,
            flags=re.DOTALL,
        )

        if generic_fence:

            code = (
                generic_fence.group(1)
                .strip()
            )

            if code.lower().startswith(
                "python"
            ):

                code = code[
                    len("python"):
                ].strip()

            return code

        # No fence.
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

        if "```" not in text:
            return ""

        parts = text.split("```")

        if len(parts) < 3:
            return ""

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