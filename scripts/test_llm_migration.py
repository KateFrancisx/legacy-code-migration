from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from pipeline.llm.gemini_migrator import (
    GeminiMigrator,
)


def main():

    source_code = """def greet(name):
    print "Hello", name
"""

    prompt = f"""
You are a Python 2 to Python 3 migration engine.

Migrate the following code from Python 2 to Python 3.

Preserve behavior.

Return ONLY the migrated Python 3 code.
Do not use Markdown code fences.
Do not explain your answer.

SOURCE:

{source_code}
"""

    migrator = GeminiMigrator()

    result = migrator.migrate(
        source_code=source_code,
        prompt=prompt,
    )

    print("=" * 70)
    print("LLM MIGRATION TEST")
    print("=" * 70)

    print()
    print("Success:", result.success)
    print("Provider:", result.provider)
    print("Model:", result.model)

    print()
    print("MIGRATED CODE")
    print("-" * 70)
    print(result.migrated_code)

    if result.error:

        print()
        print("ERROR")
        print("-" * 70)
        print(result.error)


if __name__ == "__main__":
    main()