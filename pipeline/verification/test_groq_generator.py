import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(
    0,
    r"D:\Projects\legacy-code-migration"
)

from pipeline.verification.test_generator import (
    generate_cases_for_callable,
)


REPOSITORY = (
    r"C:\Users\RIYA\OneDrive\Downloads"
    r"\python2_migration_test_repo"
    r"\python2_migration_test_repo"
)


callable_info = {
    "file": "utils.py",
    "qualified_name": "normalize_name",
    "function_name": "normalize_name",
    "kind": "function",
    "class_name": None,
    "parameters": ["name"],
}


print()
print("=" * 70)
print("GROQ BEHAVIORAL TEST GENERATION TEST")
print("=" * 70)

print("API key present:")
print(bool(os.environ.get("GROQ_API_KEY")))

print(
    "Model:",
    os.environ.get(
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    )
)

print()
print("Testing:")
print("utils.py -> normalize_name")
print("Requested cases: 3")
print("=" * 70)


try:
    cases = generate_cases_for_callable(
        callable_info=callable_info,
        count=3,
        repository_path=REPOSITORY,
    )

except Exception as exc:
    print()
    print("=" * 70)
    print("TEST FAILED")
    print("=" * 70)
    print(
        type(exc).__name__,
        ":",
        str(exc),
    )
    print("=" * 70)
    raise SystemExit(1)


print()
print("=" * 70)
print("TEST PASSED")
print("=" * 70)

print(
    json.dumps(
        [
            case.to_dict()
            for case in cases
        ],
        indent=2,
        ensure_ascii=False,
    )
)

print("=" * 70)