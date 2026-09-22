import ast
import json
from dataclasses import dataclass, asdict
from pathlib import Path

from pipeline.llm.gemini_migrator import GeminiMigrator


@dataclass
class TestCase:
    """
    Represents one behavioral test case.

    Gemini provides candidate inputs when available.
    Deterministic fallback generation is used when
    Gemini is unavailable.

    The differential executor determines whether
    original and migrated behavior actually match.
    """

    name: str
    function: str | None
    inputs: list
    expected_type: str | None = None

    def to_dict(self):
        return asdict(self)


def normalize_parameter(parameter):
    """
    Normalize parameter information.
    """

    if isinstance(parameter, str):
        return {
            "name": parameter,
            "type": None,
        }

    if isinstance(parameter, dict):
        return {
            "name": parameter.get("name"),
            "type": (
                parameter.get("type")
                or parameter.get("annotation")
                or parameter.get("inferred_type")
            ),
        }

    return {
        "name": None,
        "type": None,
    }


def normalize_type(type_name):
    """
    Normalize known parameter types.
    """

    if not type_name:
        return "unknown"

    value = str(type_name).lower().strip()

    if value in {"int", "integer"}:
        return "int"

    if value in {"float", "double"}:
        return "float"

    if value in {"str", "string", "unicode"}:
        return "str"

    if value in {"bool", "boolean"}:
        return "bool"

    if value in {"list", "array"}:
        return "list"

    if value == "tuple":
        return "tuple"

    if value in {
        "dict",
        "dictionary",
        "mapping",
    }:
        return "dict"

    if value == "set":
        return "set"

    if value in {
        "none",
        "nonetype",
        "null",
    }:
        return "none"

    return "unknown"


def candidate_values(type_name):
    """
    Conservative fallback values.

    These values are used when Gemini is unavailable,
    including API quota exhaustion.
    """

    parameter_type = normalize_type(
        type_name
    )

    if parameter_type == "int":
        return [
            0,
            1,
            -1,
            10,
        ]

    if parameter_type == "float":
        return [
            0.0,
            1.0,
            -1.0,
            10.5,
        ]

    if parameter_type == "str":
        return [
            "",
            "test",
            "hello world",
        ]

    if parameter_type == "bool":
        return [
            True,
            False,
        ]

    if parameter_type == "list":
        return [
            [],
            [1],
            [1, 2, 3],
        ]

    if parameter_type == "tuple":
        return [
            (),
            (1,),
            (1, 2, 3),
        ]

    if parameter_type == "dict":
        return [
            {},
            {"key": "value"},
        ]

    if parameter_type == "set":
        return [
            set(),
            {1},
            {1, 2},
        ]

    if parameter_type == "none":
        return [
            None
        ]

    return [
        None
    ]


def generate_no_argument_case(
    function_name,
):
    """
    Generate a case for a function without parameters.
    """

    return TestCase(
        name="no_argument_case",
        function=function_name,
        inputs=[],
    )


def generate_basic_cases(function_info):
    """
    Generate conservative deterministic fallback cases.
    """

    function_name = function_info.get(
        "name"
    )

    parameters = function_info.get(
        "parameters",
        [],
    )

    if not parameters:
        return [
            generate_no_argument_case(
                function_name
            )
        ]

    normalized_parameters = [
        normalize_parameter(parameter)
        for parameter in parameters
    ]

    cases = []

    default_inputs = []

    for parameter in normalized_parameters:
        values = candidate_values(
            parameter["type"]
        )

        default_inputs.append(
            values[0]
        )

    cases.append(
        TestCase(
            name="combined_default_case",
            function=function_name,
            inputs=default_inputs,
        )
    )

    for parameter_index, parameter in enumerate(
        normalized_parameters
    ):
        parameter_values = candidate_values(
            parameter["type"]
        )

        for value_index, value in enumerate(
            parameter_values
        ):
            inputs = []

            for index, other_parameter in enumerate(
                normalized_parameters
            ):
                other_values = candidate_values(
                    other_parameter["type"]
                )

                if index == parameter_index:
                    inputs.append(value)
                else:
                    inputs.append(
                        other_values[0]
                    )

            parameter_name = (
                parameter["name"]
                or (
                    f"parameter_"
                    f"{parameter_index + 1}"
                )
            )

            cases.append(
                TestCase(
                    name=(
                        f"{parameter_name}_variation_"
                        f"{value_index + 1}"
                    ),
                    function=function_name,
                    inputs=inputs,
                    expected_type=parameter["type"],
                )
            )

    return cases


def generate_cases_for_functions(
    functions,
):
    """
    Generate deterministic fallback behavioral cases
    for multiple functions.
    """

    cases = []

    for function_info in functions:
        cases.extend(
            generate_basic_cases(
                function_info
            )
        )

    return cases


def deduplicate_cases(cases):
    """
    Remove duplicate cases.
    """

    seen = set()
    unique = []

    for case in cases:
        key = (
            case.function,
            tuple(
                repr(value)
                for value in case.inputs
            ),
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(case)

    return unique


def extract_function_parameters(
    source_code,
    function_name,
):
    """
    Extract the real parameter names from a Python
    function using the AST.
    """

    tree = ast.parse(
        source_code
    )

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            if node.name != function_name:
                continue

            parameters = []

            positional_arguments = list(
                getattr(
                    node.args,
                    "posonlyargs",
                    [],
                )
            )

            positional_arguments.extend(
                node.args.args
            )

            for argument in positional_arguments:
                parameters.append(
                    argument.arg
                )

            if node.args.vararg:
                parameters.append(
                    node.args.vararg
                )

            for argument in node.args.kwonlyargs:
                parameters.append(
                    argument.arg
                )

            if node.args.kwarg:
                parameters.append(
                    node.args.kwarg
                )

            return parameters

    raise ValueError(
        f"Function '{function_name}' "
        "was not found in source code."
    )


def extract_function_source(
    source_code,
    function_name,
):
    """
    Extract the source of one function from
    a Python source file.
    """

    tree = ast.parse(
        source_code
    )

    lines = source_code.splitlines(
        keepends=True
    )

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        if node.name != function_name:
            continue

        start_line = (
            node.lineno - 1
        )

        end_line = getattr(
            node,
            "end_lineno",
            None,
        )

        if end_line is None:
            return source_code

        return "".join(
            lines[
                start_line:end_line
            ]
        )

    raise ValueError(
        f"Function '{function_name}' "
        "was not found in source code."
    )


def _build_fallback_cases(
    source_code,
    function_name,
    parameter_names,
):
    """
    Build deterministic behavioral cases when
    Gemini cannot generate cases.
    """

    function_info = {
        "name": function_name,
        "parameters": [
            {
                "name": name,
                "type": None,
            }
            for name in parameter_names
        ],
        "source": source_code,
    }

    return deduplicate_cases(
        generate_basic_cases(
            function_info
        )
    )


def generate_llm_cases(
    source_code,
    function_name,
    parameter_names=None,
    count=5,
):
    """
    Generate behavioral inputs using Gemini.

    Gemini is preferred when available.

    If Gemini fails because of quota, rate limits,
    temporary API errors, invalid responses, or any
    other generation failure, deterministic fallback
    cases are returned instead.

    The differential executor, not Gemini, determines
    whether behavior is equivalent.
    """

    if parameter_names is None:
        parameter_names = (
            extract_function_parameters(
                source_code,
                function_name,
            )
        )

    parameter_text = ", ".join(
        parameter_names
    )

    prompt = f"""
You are generating behavioral test inputs for a
Python 2-to-Python 3 migration verification system.

Function name:
{function_name}

Parameters:
{parameter_text}

Source code:
{source_code}

Generate exactly {count} different behavioral
test cases for THIS FUNCTION.

The inputs array MUST contain exactly the arguments
required by the function, in the same order as the
parameters.

Return ONLY valid JSON.

The response MUST be a JSON array.

Each item MUST have exactly these fields:

{{
    "function": "{function_name}",
    "inputs": []
}}

Example:

[
    {{
        "function": "{function_name}",
        "inputs": [100, 10]
    }}
]

Important:

- Use the actual function parameters.
- Use values appropriate for the parameter's role.
- Do not invent extra arguments.
- Do not create UI tests.
- Do not create API tests.
- Do not create unrelated tests.
- Do not include descriptions.
- Do not include titles.
- Do not include expected results.
- Do not include explanations.
- Do not include markdown.
- Do not use code fences.
- Do not include any fields other than
  "function" and "inputs".
"""

    try:
        response = GeminiMigrator().migrate(
            source_code,
            prompt,
        )

        if not response.success:
            raise RuntimeError(
                str(response.error)
            )

        raw_response = (
            response.raw_response.strip()
        )

        if raw_response.startswith("```"):
            lines = raw_response.splitlines()

            if lines:
                lines = lines[1:]

            if (
                lines
                and lines[-1].strip()
                == "```"
            ):
                lines = lines[:-1]

            raw_response = "\n".join(
                lines
            ).strip()

        generated = json.loads(
            raw_response
        )

        if not isinstance(
            generated,
            list,
        ):
            raise ValueError(
                "Gemini response must be a JSON array."
            )

        expected_parameter_count = len(
            parameter_names
        )

        cases = []

        for index, item in enumerate(
            generated
        ):
            if not isinstance(
                item,
                dict,
            ):
                continue

            if set(item.keys()) != {
                "function",
                "inputs",
            }:
                continue

            if item["function"] != function_name:
                continue

            inputs = item["inputs"]

            if not isinstance(
                inputs,
                list,
            ):
                continue

            if len(inputs) != expected_parameter_count:
                continue

            cases.append(
                TestCase(
                    name=(
                        f"llm_case_{index + 1}"
                    ),
                    function=function_name,
                    inputs=inputs,
                )
            )

        cases = deduplicate_cases(
            cases
        )

        if cases:
            return cases[:count]

        raise ValueError(
            "Gemini returned no valid behavioral "
            "test cases."
        )

    except Exception:
        # Gemini is a candidate-input generator only.
        # Verification must continue even when the API
        # is unavailable or its quota is exhausted.
        fallback_cases = (
            _build_fallback_cases(
                source_code=source_code,
                function_name=function_name,
                parameter_names=parameter_names,
            )
        )

        if not fallback_cases:
            raise RuntimeError(
                "Unable to generate behavioral "
                f"cases for {function_name}."
            )

        return fallback_cases[:count]


def generate_llm_cases_from_file(
    file_path,
    function_name,
    count=5,
):
    """
    Read a source file, extract one function,
    extract its real parameters, and generate
    behavioral cases.

    Gemini is used when available. Deterministic
    fallback generation is used automatically when
    Gemini is unavailable.
    """

    source_path = Path(
        file_path
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"Source file not found: "
            f"{source_path}"
        )

    source_code = (
        source_path.read_text(
            encoding="utf-8"
        )
    )

    function_source = (
        extract_function_source(
            source_code,
            function_name,
        )
    )

    parameter_names = (
        extract_function_parameters(
            source_code,
            function_name,
        )
    )

    return generate_llm_cases(
        source_code=function_source,
        function_name=function_name,
        parameter_names=parameter_names,
        count=count,
    )


def generate_llm_cases_for_functions(
    repository_path,
    file_name,
    function_names,
    count=5,
):
    """
    Generate behavioral cases for multiple
    functions in one source file.

    Returns:

        {
            function_name: [TestCase, ...]
        }
    """

    file_path = (
        Path(repository_path)
        / file_name
    )

    results = {}

    for function_name in function_names:
        results[function_name] = (
            generate_llm_cases_from_file(
                file_path=file_path,
                function_name=function_name,
                count=count,
            )
        )

    return results