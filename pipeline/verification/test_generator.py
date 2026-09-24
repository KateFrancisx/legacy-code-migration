import json
import os
from dataclasses import dataclass, field
from pathlib import Path


# Behavioral test scenario generation uses Groq.
# Differential execution remains responsible for deciding whether
# the generated scenarios reveal behavioral differences.


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
        return {
            "function": self.function,
            "inputs": self.inputs,
            "constructor_inputs": (
                self.constructor_inputs
            ),
            "metadata": self.metadata,
        }


def _safe_json_value(value):
    if isinstance(
        value,
        dict,
    ):
        return {
            key: _safe_json_value(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        list,
    ):
        return [
            _safe_json_value(item)
            for item in value
        ]

    if isinstance(
        value,
        tuple,
    ):
        return tuple(
            _safe_json_value(item)
            for item in value
        )

    if isinstance(
        value,
        str,
    ):
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


def _effective_parameters(
    callable_info,
):
    """
    Return parameters that the caller must actually provide.

    Removes self/cls for methods and constructors.
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

    constructor_description = (
        _callable_description(
            constructor_info
        )
        if constructor_info is not None
        else {}
    )

    constructor_parameters = (
        constructor_description.get(
            "parameters",
            [],
        )
    )

    constructor_name = (
        constructor_description.get(
            "qualified_name"
        )
        if constructor_description
        else None
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

Constructor:
{constructor_name}

Constructor parameters:
{json.dumps(constructor_parameters)}

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

For module-level functions:

- "inputs" contains the function arguments.
- "constructor_inputs" should be omitted or null.

For constructors:

- "inputs" contains the constructor arguments.
- "constructor_inputs" should be omitted or null.

For instance methods:

- The object must first be constructed.
- "constructor_inputs" MUST contain valid arguments for the
  discovered constructor.
- "inputs" contains the arguments passed to the method.
- Do not put constructor arguments inside "inputs".
- The constructor parameters shown above must be respected.

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

Example for an instance method whose constructor requires
["name", "items"] and whose method takes no arguments:

[
  {{
    "constructor_inputs": ["example", []],
    "inputs": []
  }}
]
"""

    return prompt


def _extract_json_array(
    text,
):
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
    if not repository_path:
        return ""

    if not file_name:
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


def _generate_with_groq(
    prompt,
):
    """
    Generate behavioral test scenarios using Groq.

    Configuration:
        GROQ_API_KEY  - required API key
        GROQ_MODEL    - optional model name

    Default model:
        openai/gpt-oss-120b

    The LLM is used only to propose behavioral scenarios.
    The generated scenarios are normalized and validated by
    the existing code below; correctness is established later
    by the differential executor.
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
        return []

    try:
        from groq import Groq
    except ImportError:
        return []

    model = os.environ.get(
        "GROQ_MODEL",
        "openai/gpt-oss-120b",
    )

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
                        "You generate behavioral test scenarios "
                        "for Python callables. "
                        "Return ONLY valid JSON. "
                        "Do not return markdown or explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.1,
        )

        response_text = getattr(
            response.choices[0].message,
            "content",
            None,
        )

        return _extract_json_array(
            response_text
        )

    except Exception:
        return []


def _parameter_count(
    callable_info,
):
    return len(
        _effective_parameters(
            callable_info
        )
    )


def _fallback_value_for_parameter(
    parameter_name,
    position,
):
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
    parameters = _effective_parameters(
        callable_info
    )

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
    constructor_info=None,
):
    """
    Build constructor arguments from the actual discovered
    constructor.

    This is deliberately repository-independent.
    """

    if constructor_info is None:
        return []

    return _fallback_inputs(
        constructor_info
    )


def _normalize_constructor_inputs(
    case,
    constructor_info,
):
    """
    Ensure an instance-method case has enough constructor
    arguments to instantiate the discovered class.

    LLM-generated constructor inputs are preserved when they
    are complete. Missing or empty constructor inputs fall
    back to values derived from the constructor signature.
    """

    if constructor_info is None:
        if case.constructor_inputs is None:
            case.constructor_inputs = []

        return case

    fallback = _fallback_constructor_inputs(
        callable_info=None,
        constructor_info=constructor_info,
    )

    if case.constructor_inputs is None:
        case.constructor_inputs = fallback
        return case

    if not isinstance(
        case.constructor_inputs,
        list,
    ):
        case.constructor_inputs = fallback
        return case

    if len(case.constructor_inputs) < len(
        fallback
    ):
        case.constructor_inputs = fallback

    return case


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
            case = _normalize_constructor_inputs(
                case=case,
                constructor_info=constructor_info,
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

            constructor_inputs = (
                _fallback_constructor_inputs(
                    callable_info=callable_info,
                    constructor_info=constructor_info,
                )
            )

            cases.append(
                BehavioralTestCase(
                    function=description.get(
                        "function_name"
                    ),
                    inputs=[],
                    constructor_inputs=(
                        constructor_inputs
                    ),
                    metadata={
                        "generation": "fallback",
                        "constructor_discovered": (
                            constructor_info
                            is not None
                        ),
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
    Generate behavioral cases for every discovered callable.

    Instance methods are automatically associated with the
    constructor belonging to the same file and class.
    """

    results = {}

    constructors = {}

    for callable_info in callables:

        description = _callable_description(
            callable_info
        )

        if description.get(
            "kind"
        ) != "constructor":
            continue

        key = (
            description.get(
                "file"
            ),
            description.get(
                "class_name"
            ),
        )

        constructors[
            key
        ] = callable_info

    for callable_info in callables:

        description = _callable_description(
            callable_info
        )

        qualified_name = description.get(
            "qualified_name"
        )

        constructor_info = None

        if description.get(
            "kind"
        ) == "instance_method":

            key = (
                description.get(
                    "file"
                ),
                description.get(
                    "class_name"
                ),
            )

            constructor_info = constructors.get(
                key
            )

        results[
            qualified_name
        ] = generate_cases_for_callable(
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

        results[
            function_name
        ] = cases

    return results