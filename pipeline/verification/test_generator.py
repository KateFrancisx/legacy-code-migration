import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BehavioralTestCase:
    """
    One generated behavioral scenario.

    For module-level functions:

        inputs = [...]
        constructor_inputs = None

    For class methods:

        constructor_inputs = [...]
        inputs = [...]

    The structure is intentionally generic and does not
    depend on any specific repository.
    """

    function: str
    inputs: list = field(
        default_factory=list
    )
    constructor_inputs: list = None
    metadata: dict = field(
        default_factory=dict
    )

    def to_dict(self):
        """
        Convert the test case to a JSON-friendly dictionary.
        """

        return {
            "function": self.function,
            "inputs": self.inputs,
            "constructor_inputs": (
                self.constructor_inputs
            ),
            "metadata": self.metadata,
        }


def _safe_json_value(value):
    """
    Normalize values produced by an LLM or JSON parser.

    JSON null is converted to Python None automatically by
    json.loads(). This function additionally handles nested
    structures and common accidental string representations.
    """

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
    """
    Normalize one generated scenario.

    The function accepts both:

        {"inputs": [...]}

    and:

        {
            "inputs": [...],
            "constructor_inputs": [...]
        }

    The callable name comes from trusted callable metadata,
    not from the generated text.
    """

    if isinstance(
        raw_case,
        dict,
    ):

        inputs = raw_case.get(
            "inputs",
            [],
        )

        constructor_inputs = raw_case.get(
            "constructor_inputs"
        )

        metadata = raw_case.get(
            "metadata",
            {},
        )

    elif isinstance(
        raw_case,
        list,
    ):

        inputs = raw_case

        constructor_inputs = None

        metadata = {}

    else:

        inputs = [
            raw_case
        ]

        constructor_inputs = None

        metadata = {}

    if inputs is None:
        inputs = []

    if constructor_inputs is not None:
        constructor_inputs = _safe_json_value(
            constructor_inputs
        )

    inputs = _safe_json_value(
        inputs
    )

    if not isinstance(
        inputs,
        list,
    ):
        inputs = [
            inputs
        ]

    if (
        constructor_inputs is not None
        and not isinstance(
            constructor_inputs,
            list,
        )
    ):
        constructor_inputs = [
            constructor_inputs
        ]

    return BehavioralTestCase(
        function=function_name,
        inputs=inputs,
        constructor_inputs=constructor_inputs,
        metadata=(
            metadata
            if isinstance(
                metadata,
                dict,
            )
            else {}
        ),
    )


def _callable_description(
    callable_info,
):
    """
    Build a generic description of a callable for an LLM.

    callable_info may be either a CallableInfo object or a
    dictionary produced by CallableInfo.to_dict().
    """

    if callable_info is None:
        return {}

    if isinstance(
        callable_info,
        dict,
    ):
        return callable_info

    if hasattr(
        callable_info,
        "to_dict",
    ):
        return callable_info.to_dict()

    return {
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


def _build_llm_prompt(
    callable_info,
    count,
    source_text=None,
):
    """
    Build a repository-independent behavioral test
    generation prompt.

    The LLM proposes candidate inputs only.

    Correctness is determined later by differential
    execution against Python 2 and Python 3.
    """

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

    if source_text is None:
        source_text = ""

    prompt = f"""
Generate {count} behavioral test scenarios for a Python
callable.

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

Relevant source:
{source_text}

Rules:

1. Return ONLY valid JSON.
2. Return a JSON array.
3. Each item must be an object.
4. Each item must contain "inputs".
5. "inputs" must always be a JSON array.
6. JSON null is allowed and represents Python None.
7. Do not return Python expressions as strings.
8. Do not return executable code.
9. Use values appropriate for the callable's parameters.
10. Include ordinary cases and useful boundary cases.
11. Do not invent a function name.
12. Do not include the callable name in the inputs.

For class methods:

- "constructor_inputs" must contain the arguments required
  to construct the object.
- "inputs" must contain the arguments passed to the method.

For constructors:

- "inputs" contains the constructor arguments.
- "constructor_inputs" should be omitted or null.

For module-level functions:

- "inputs" contains the function arguments.
- "constructor_inputs" should be omitted or null.

Example for a module function with parameters
["value", "percentage"]:

[
  {{
    "inputs": [100, 10]
  }},
  {{
    "inputs": [0, 50]
  }}
]

Example for an instance method:

[
  {{
    "constructor_inputs": ["example"],
    "inputs": []
  }}
]
"""

    return prompt


def _extract_json_array(
    text,
):
    """
    Extract a JSON array from an LLM response.
    """

    if not text:
        return []

    text = text.strip()

    try:

        value = json.loads(
            text
        )

        if isinstance(
            value,
            list,
        ):
            return value

    except Exception:
        pass

    start = text.find(
        "["
    )

    end = text.rfind(
        "]"
    )

    if (
        start >= 0
        and end > start
    ):

        candidate = text[
            start:end + 1
        ]

        try:

            value = json.loads(
                candidate
            )

            if isinstance(
                value,
                list,
            ):
                return value

        except Exception:
            pass

    return []


def _load_source(
    repository_path,
    file_name,
):
    """
    Load the migrated source for contextual generation.

    Source loading is best-effort. Failure does not prevent
    fallback case generation.
    """

    if not repository_path:
        return ""

    path = (
        Path(repository_path)
        / file_name
    )

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


def _generate_with_gemini(
    prompt,
):
    """
    Generate cases with Gemini when available.

    This function intentionally keeps the LLM optional.
    Differential execution remains the source of truth.
    """

    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not api_key:
        return []

    try:

        from google import genai

    except ImportError:
        return []

    try:

        client = genai.Client(
            api_key=api_key
        )

        response = (
            client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
        )

        text = getattr(
            response,
            "text",
            None,
        )

        return _extract_json_array(
            text
        )

    except Exception:
        return []


def _parameter_count(
    callable_info,
):
    """
    Determine the number of user-supplied parameters.

    self and cls are excluded for methods.
    """

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

    return len(parameters)


def _fallback_value_for_parameter(
    parameter_name,
    position,
):
    """
    Produce a conservative generic fallback value.

    This is intentionally type-agnostic.

    The fallback generator is not expected to understand
    arbitrary domain objects. Its job is to provide basic
    primitive candidates when an LLM is unavailable.
    """

    name = (
        parameter_name
        or ""
    ).lower()

    if any(
        token in name
        for token in (
            "name",
            "customer",
            "user",
            "title",
            "label",
            "text",
        )
    ):
        return "example"

    if any(
        token in name
        for token in (
            "percent",
            "percentage",
            "rate",
        )
    ):
        return 10

    if any(
        token in name
        for token in (
            "size",
            "count",
            "quantity",
            "limit",
            "index",
        )
    ):
        return 2

    if any(
        token in name
        for token in (
            "items",
            "values",
            "data",
            "records",
            "entries",
        )
    ):
        return []

    if position == 0:
        return 1

    return 1


def _fallback_inputs(
    callable_info,
):
    """
    Generate conservative inputs from parameter metadata.
    """

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

    return [
        _fallback_value_for_parameter(
            parameter_name,
            position,
        )
        for position, parameter_name in enumerate(
            parameters
        )
    ]


def _fallback_constructor_inputs(
    callable_info,
):
    """
    Generate fallback constructor inputs for an instance
    method.

    The constructor metadata must be supplied by the caller
    when available.
    """

    return _fallback_inputs(
        callable_info
    )


def _normalize_generated_cases(
    callable_info,
    raw_cases,
    count,
):
    """
    Normalize and limit generated scenarios.
    """

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

            if (
                case.constructor_inputs
                is None
            ):
                case.constructor_inputs = (
                    _fallback_constructor_inputs(
                        callable_info
                    )
                )

        normalized.append(
            case
        )

        if len(normalized) >= count:
            break

    return normalized


def generate_cases_for_callable(
    callable_info,
    count=3,
    repository_path=None,
    source_text=None,
):
    """
    Generate behavioral cases for one generic callable.

    LLM generation is attempted first when available.

    If the LLM is unavailable or returns invalid data,
    deterministic fallback cases are generated.
    """

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
    )

    raw_cases = _generate_with_gemini(
        prompt
    )

    cases = _normalize_generated_cases(
        callable_info=callable_info,
        raw_cases=raw_cases,
        count=count,
    )

    if len(cases) >= count:
        return cases

    fallback_inputs = _fallback_inputs(
        callable_info
    )

    kind = description.get(
        "kind",
        "function",
    )

    while len(cases) < count:

        if kind == "instance_method":

            cases.append(
                BehavioralTestCase(
                    function=description.get(
                        "function_name"
                    ),
                    inputs=[],
                    constructor_inputs=(
                        fallback_inputs
                    ),
                    metadata={
                        "generation": "fallback"
                    },
                )
            )

        else:

            cases.append(
                BehavioralTestCase(
                    function=description.get(
                        "function_name"
                    ),
                    inputs=(
                        list(
                            fallback_inputs
                        )
                    ),
                    constructor_inputs=None,
                    metadata={
                        "generation": "fallback"
                    },
                )
            )

    return cases


def generate_cases_for_callables(
    callables,
    count=3,
    repository_path=None,
):
    """
    Generate behavioral cases for multiple CallableInfo
    objects.

    Returns:

        {
            "qualified.name": [BehavioralTestCase, ...]
        }
    """

    results = {}

    for callable_info in callables:

        description = _callable_description(
            callable_info
        )

        qualified_name = description.get(
            "qualified_name"
        )

        results[
            qualified_name
        ] = generate_cases_for_callable(
            callable_info=callable_info,
            count=count,
            repository_path=repository_path,
        )

    return results


def generate_llm_cases_for_functions(
    repository_path,
    file_name,
    function_names,
    count=3,
):
    """
    Backward-compatible interface used by the existing
    semantic verifier.

    This interface remains available while the verifier is
    migrated to the generic CallableInfo-based interface.

    It generates cases for module-level functions only.

    Class methods should use generate_cases_for_callable()
    with CallableInfo metadata.
    """

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

        results[
            function_name
        ] = cases

    return results