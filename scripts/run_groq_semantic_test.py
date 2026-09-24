from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# ============================================================
# THIRD-PARTY IMPORTS
# ============================================================

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# PROJECT IMPORTS
# ============================================================

from pipeline.semantic_equivalence.predictor import (
    predict_semantic_equivalence,
)


# ============================================================
# CONFIG
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")

MODEL = "openai/gpt-oss-120b"

REPO_PATH = Path(
    r"C:\Users\KATE\Downloads\python2_migration_test_repo"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"

PROMPT_FILE = (
    OUTPUT_DIR
    / f"{REPO_PATH.name}_llm_prompts.json"
)

CONTEXT_FILE = (
    OUTPUT_DIR
    / f"{REPO_PATH.name}_migration_context.json"
)

RESULT_FILE = (
    OUTPUT_DIR
    / f"{REPO_PATH.name}_groq_semantic_test.json"
)


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_code(response: str) -> str:
    """
    Extract Python code from an LLM response.

    Handles:
        ```python
        code
        ```

    and plain responses.
    """

    match = re.search(
        r"```(?:python|py)?\s*(.*?)```",
        response,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return response.strip()


def find_context(contexts, target_file):
    for ctx in contexts:

        if not isinstance(ctx, dict):
            continue

        target = ctx.get("target", {})

        if (
            isinstance(target, dict)
            and target.get("file") == target_file
        ):
            return ctx

    return {}


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("GROQ → CODEBERT SEMANTIC EQUIVALENCE SMOKE TEST")
    print("=" * 70)

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print()
        print("ERROR: GROQ_API_KEY is not configured.")
        print()
        print("Add it to your .env file:")
        print("GROQ_API_KEY=your_key_here")
        sys.exit(1)

    if not PROMPT_FILE.exists():
        print()
        print(f"ERROR: Prompt file not found:")
        print(PROMPT_FILE)
        print()
        print("Run the pre-LLM pipeline first.")
        sys.exit(1)

    if not CONTEXT_FILE.exists():
        print()
        print(f"ERROR: Context file not found:")
        print(CONTEXT_FILE)
        print()
        print("Run the pre-LLM pipeline first.")
        sys.exit(1)

    prompts = load_json(PROMPT_FILE)
    contexts = load_json(CONTEXT_FILE)

    client = Groq(api_key=api_key)

    print()
    print(f"Provider : Groq")
    print(f"Model    : {MODEL}")
    print(f"Repository: {REPO_PATH}")
    print()

    results = []

    # --------------------------------------------------------
    # Test only the first 3 migration candidates
    # --------------------------------------------------------

    for index, item in enumerate(
        prompts[:3],
        start=1,
    ):

        if not isinstance(item, dict):
            continue

        target_file = item.get("file", "")
        prompt = item.get("prompt", "")

        if not target_file or not prompt:
            continue

        context = find_context(
            contexts,
            target_file,
        )

        source_code = (
            context
            .get("target", {})
            .get("source_code", "")
        )

        if not source_code:

            source_path = (
                REPO_PATH
                / target_file
            )

            if source_path.exists():
                source_code = (
                    source_path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    )
                )

        print("-" * 70)
        print(
            f"[{index}/3] Migrating: "
            f"{target_file}"
        )

        try:

            # ------------------------------------------------
            # GROQ MIGRATION
            # ------------------------------------------------

            response = client.chat.completions.create(

                model=MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert Python 2 to Python 3 "
                            "migration engineer. "
                            "Migrate the supplied legacy code to "
                            "Python 3 while preserving behavior. "
                            "Return ONLY the migrated Python code. "
                            "Do not explain the changes."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"{prompt}\n\n"
                            "SOURCE CODE:\n"
                            "```python\n"
                            f"{source_code}\n"
                            "```\n\n"
                            "Return ONLY the complete migrated "
                            "Python 3 code."
                        ),
                    },
                ],

                temperature=0.1,

                max_completion_tokens=8192,
            )

            raw_response = (
                response
                .choices[0]
                .message
                .content
            )

            migrated_code = extract_code(
                raw_response
            )

            print()
            print("  [SUCCESS] Groq migration generated")
            print(
                f"  Generated code: "
                f"{len(migrated_code)} chars"
            )

            # ------------------------------------------------
            # CODEBERT SEMANTIC EQUIVALENCE
            # ------------------------------------------------

            semantic_result = (
                predict_semantic_equivalence(
                    original_code=source_code,
                    migrated_code=migrated_code,
                )
            )

            print()
            print("  Semantic Equivalence:")
            print(
                f"    Prediction : "
                f"{semantic_result['prediction'].upper()}"
            )
            print(
                f"    Confidence : "
                f"{semantic_result['confidence']:.2%}"
            )

            print()
            print("  Probabilities:")
            print(
                f"    Equivalent     : "
                f"{semantic_result['probabilities']['equivalent']:.2%}"
            )
            print(
                f"    Not Equivalent: "
                f"{semantic_result['probabilities']['not_equivalent']:.2%}"
            )

            results.append(
                {
                    "file": target_file,
                    "llm": {
                        "provider": "groq",
                        "model": MODEL,
                        "success": True,
                        "migrated_code": migrated_code,
                    },
                    "semantic_equivalence":
                        semantic_result,
                }
            )

        except Exception as exc:

            print()
            print(
                f"  [FAILED] {type(exc).__name__}: "
                f"{exc}"
            )

            results.append(
                {
                    "file": target_file,
                    "llm": {
                        "provider": "groq",
                        "model": MODEL,
                        "success": False,
                        "error": str(exc),
                    },
                }
            )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    RESULT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RESULT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    successful = sum(
        1
        for r in results
        if r.get("llm", {}).get("success")
    )

    semantic_results = [
        r
        for r in results
        if "semantic_equivalence" in r
    ]

    print()
    print("=" * 70)
    print("GROQ SEMANTIC TEST SUMMARY")
    print("=" * 70)

    print(
        f"LLM successful        : "
        f"{successful}/{len(results)}"
    )

    print(
        f"Semantic predictions  : "
        f"{len(semantic_results)}"
    )

    print()
    print(
        f"Results saved to:"
    )
    print(RESULT_FILE)

    print()


if __name__ == "__main__":
    main()