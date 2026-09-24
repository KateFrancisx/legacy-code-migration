import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BehavioralTestCase:
    """
    One LLM-generated behavioral scenario.

    For module-level functions:
        inputs = [...]
        constructor_inputs = None

    For class methods:
        constructor_inputs = [...]
        inputs = [...]
    """

    function: str
    inputs: list = field(default_factory=list)
    constructor_inputs: list = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "function": self.function,
            "inputs": self.inputs,
            "constructor_inputs": self.constructor_inputs,
            "metadata": self.metadata,
        }


def _safe_json_value(value):
    if isinstance(value, dict):
        return {
            key: _safe_json_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _safe_json_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _safe_json_value(item)
            for item in value
        )

    if isinstance(value, str):
        stripped = value.strip()

        if stripped == "null":
            return None

        if stripped == "None":
            return None

    return value


def _normalize_case(
    function_name,
    raw_case,
    callable_info=None,
):
    if isinstance(raw_case, dict):
        inputs = raw_case.get("inputs", [])
        constructor_inputs = raw_case.get("constructor_inputs")
        metadata = raw_case.get("metadata", {})

    elif isinstance(raw_case, list):
        inputs = raw_case
        constructor_inputs = None
        metadata = {}

    else:
        inputs = [raw_case]
        constructor_inputs = None
        metadata = {}

    if inputs is None:
        inputs = []

    if constructor_inputs is not None:
        constructor_inputs = _safe_json_value(
            constructor_inputs
        )

    inputs = _safe_json_value(inputs)

    if not isinstance(inputs, list):
        inputs = [inputs]

    if (
        constructor_inputs is not None
        and not isinstance(constructor_inputs, list)
    ):
        constructor_inputs = [constructor_inputs]

    return BehavioralTestCase(
        function=function_name,
        inputs=inputs,
        constructor_inputs=constructor_inputs,
        metadata=(
            metadata
            if isinstance(metadata, dict)
            else {}
        ),
    )


def _callable_description(callable_info):
    if callable_info is None:
        return {}

    if isinstance(callable_info, dict):
        return callable_info

    if hasattr(callable_info, "to_dict"):
        return callable_info.to_dict()

    return {
        "file": getattr(
            callable_info,
            "file_name",
            None,
        ),
        "qualified_name": getattr(
            callable_info,
            "qualified_name",
            None,
        ),
        "function_name": getattr(
            callable_info,
            "function_name",
            None,
        ),
        "kind": getattr(
            callable_info,
            "kind",
            None,
        ),
        "class_name": getattr(
            callable_info,
            "class_name",
            None,
        ),
        "parameters": getattr(
            callable_info,
            "parameters",
            [],
        ),
    }


def _effective_parameters(callable_info):
    description = _callable_description(
        callable_info
    )

    parameters = list(
        description.get(
            "parameters",
            [],
        )
    )

    kind = description.get(
        "kind",
        "function",
    )

    if kind in (
        "instance_method",
        "constructor",
        "classmethod",
    ):
        if parameters and parameters[0] in (
            "self",
            "cls",
        ):
            parameters = parameters[1:]

    return parameters


def _build_llm_prompt(
    callable_info,
    count,
    source_text=None,
    constructor_info=None,
):
    description = _callable_description(
        callable_info
    )

    qualified_name = description.get(
        "qualified_name"
    )

    function_name = description.get(
        "function_name"
    )

    callable_kind = description.get(
        "kind",
        "function",
    )

    class_name = description.get(
        "class_name"
    )

    parameters = description.get(
        "parameters",
        [],
    )

    constructor_description = _callable_description(
        constructor_info
    )

    constructor_parameters = (
        constructor_description.get(
            "parameters",
            [],
        )
        if constructor_info is not None
        else []
    )

    constructor_name = (
        constructor_description.get(
            "qualified_name"
        )
        if constructor_info is not None
        else None
    )

    if source_text is None:
        source_text = ""

    prompt = f"""
Generate exactly {count} behavioral test scenarios
for this Python callable.

Callable:
{qualified_name}

Function name:
{function_name}

Callable kind:
{callable_kind}

Owning class:
{class_name}

Parameters:
{json.dumps(parameters)}

Constructor:
{constructor_name}

Constructor parameters:
{json.dumps(constructor_parameters)}

Relevant source:
{source_text}

Rules:

1. Return ONLY valid JSON.
2. Return a JSON array.
3. Return exactly {count} items.
4. Every item must be an object.
5. Every item must contain "inputs".
6. "inputs" must always be a JSON array.
7. JSON null represents Python None.
8. Do not return Python expressions as strings.
9. Do not return executable code.
10. Use values appropriate for the callable parameters.
11. Include ordinary cases and useful boundary cases.
12. Do not invent a function name.
13. Do not include the callable name inside inputs.
14. Do not include markdown.
15. Do not include explanations.

For module-level functions:

- "inputs" contains the function arguments.
- "constructor_inputs" should be omitted or null.

For constructors:

- "inputs" contains constructor arguments.
- "constructor_inputs" should be omitted or null.

For instance methods:

- "constructor_inputs" MUST contain valid constructor arguments.
- "inputs" contains only the method arguments.
- Do not put constructor arguments inside "inputs".

Example:

[
  {{"inputs": [100, 10]}},
  {{"inputs": [0, 50]}},
  {{"inputs": [-20, 150]}}
]
"""

    return prompt


def _extract_json_array(text):
    if not text:
        return []

    text = text.strip()

    try:
        value = json.loads(text)

        if isinstance(value, list):
            return value

    except Exception:
        pass

    start = text.find("[")
    end = text.rfind("]")

    if start >= 0 and end > start:
        candidate = text[start:end + 1]

        try:
            value = json.loads(candidate)

            if isinstance(value, list):
                return value

        except Exception:
            pass

    return []


def _load_source(
    repository_path,
    file_name,
):
    if not repository_path:
        return ""

    if not file_name:
        return ""

    path = Path(repository_path) / file_name

    if not path.exists():
        return ""

    try:
        return path.read_text(
            encoding="utf-8"
        )
    except (
        OSError,
        UnicodeDecodeError,
    ):
        return ""


def _generate_with_groq(prompt):
    """
    Generate behavioral scenarios using Groq.

    IMPORTANT:
    This function does NOT use fallback generation.

    If Groq fails, the exception is reported and raised.
    """

    api_key = os.environ.get(
        "GROQ_API_KEY"
    )

    if not api_key:
        try:
            from dotenv import load_dotenv

            load_dotenv()

            api_key = os.environ.get(
                "GROQ_API_KEY"
            )

        except ImportError:
            pass

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError(
            "The groq package is not installed."
        ) from exc

    model = os.environ.get(
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    )

    print()
    print("=" * 70)
    print("GROQ REQUEST")
    print("=" * 70)
    print("Model:", model)
    print()
    print(prompt)
    print("=" * 70)

    try:
        client = Groq(
            api_key=api_key
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate behavioral test "
                        "scenarios for Python callables. "
                        "Return ONLY valid JSON. "
                        "Do not return markdown. "
                        "Do not return explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.1,
        )

    except Exception as exc:
        print()
        print("=" * 70)
        print("GROQ API ERROR")
        print("=" * 70)
        print(
            type(exc).__name__,
            ":",
            str(exc),
        )
        print("=" * 70)

        raise

    response_text = getattr(
        response.choices[0].message,
        "content",
        None,
    )

    print()
    print("=" * 70)
    print("GROQ RAW RESPONSE")
    print("=" * 70)
    print(response_text)
    print("=" * 70)

    cases = _extract_json_array(
        response_text
    )

    print()
    print(
        "GROQ PARSED CASE COUNT:",
        len(cases),
    )

    if not cases:
        raise RuntimeError(
            "Groq returned a response, but it "
            "could not be parsed as a JSON array."
        )

    return cases


def _normalize_generated_cases(
    callable_info,
    raw_cases,
    count,
    constructor_info=None,
):
    description = _callable_description(
        callable_info
    )

    function_name = description.get(
        "function_name"
    )

    kind = description.get(
        "kind",
        "function",
    )

    normalized = []

    for raw_case in raw_cases:
        case = _normalize_case(
            function_name=function_name,
            raw_case=raw_case,
            callable_info=callable_info,
        )

        if kind == "instance_method":
            if constructor_info is None:
                raise RuntimeError(
                    "Instance method has no discovered constructor."
                )

            if (
                case.constructor_inputs is None
                or not isinstance(
                    case.constructor_inputs,
                    list,
                )
            ):
                raise RuntimeError(
                    "Groq did not provide valid "
                    "constructor_inputs for "
                    f"{description.get('qualified_name')}."
                )

        normalized.append(case)

    if len(normalized) != count:
        raise RuntimeError(
            f"Groq generated {len(normalized)} cases "
            f"but exactly {count} were required for "
            f"{description.get('qualified_name')}."
        )

    return normalized


def generate_cases_for_callable(
    callable_info,
    count=3,
    repository_path=None,
    source_text=None,
    constructor_info=None,
):
    if count <= 0:
        return []

    description = _callable_description(
        callable_info
    )

    if source_text is None:
        source_text = _load_source(
            repository_path=repository_path,
            file_name=description.get(
                "file"
            ),
        )

    prompt = _build_llm_prompt(
        callable_info=callable_info,
        count=count,
        source_text=source_text,
        constructor_info=constructor_info,
    )

    raw_cases = _generate_with_groq(
        prompt
    )

    cases = _normalize_generated_cases(
        callable_info=callable_info,
        raw_cases=raw_cases,
        count=count,
        constructor_info=constructor_info,
    )

    for case in cases:
        case.metadata = {
            **case.metadata,
            "generation": "groq",
            "model": os.environ.get(
                "GROQ_MODEL",
                "openai/gpt-oss-120b",
            ),
        }

    return cases


def generate_cases_for_callables(
    callables,
    count=3,
    repository_path=None,
):
    results = {}

    constructors = {}

    for callable_info in callables:
        description = _callable_description(
            callable_info
        )

        if description.get("kind") != "constructor":
            continue

        key = (
            description.get("file"),
            description.get("class_name"),
        )

        constructors[key] = callable_info

    for callable_info in callables:
        description = _callable_description(
            callable_info
        )

        qualified_name = description.get(
            "qualified_name"
        )

        constructor_info = None

        if description.get("kind") == "instance_method":
            key = (
                description.get("file"),
                description.get("class_name"),
            )

            constructor_info = constructors.get(key)

        print()
        print(
            "Generating Groq cases for:",
            qualified_name,
        )

        results[qualified_name] = generate_cases_for_callable(
            callable_info=callable_info,
            count=count,
            repository_path=repository_path,
            constructor_info=constructor_info,
        )

    return results


def generate_llm_cases_for_functions(
    repository_path,
    file_name,
    function_names,
    count=3,
):
    results = {}

    for function_name in function_names:
        callable_info = {
            "file": file_name,
            "qualified_name": function_name,
            "function_name": function_name,
            "kind": "function",
            "class_name": None,
            "parameters": [],
        }

        cases = generate_cases_for_callable(
            callable_info=callable_info,
            count=count,
            repository_path=repository_path,
        )

        results[function_name] = cases

    return results