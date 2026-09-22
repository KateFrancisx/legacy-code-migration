from dataclasses import dataclass, asdict


@dataclass
class TestCase:
    """
    A generic behavioral test case.

    The test case describes candidate inputs for a discovered
    function. It does not assume anything about a particular
    repository.
    """

    name: str
    function: str | None
    inputs: list
    expected_type: str | None = None

    def to_dict(self):
        return asdict(self)


def normalize_parameter(parameter):
    """
    Normalize parameter metadata into a predictable structure.

    Supports several possible extractor formats:

        "value"

        {
            "name": "value",
            "type": "int"
        }

        {
            "name": "value",
            "annotation": "str"
        }
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
    Convert type information into a small set of categories.

    Unknown annotations remain unknown rather than being guessed.
    """

    if not type_name:
        return "unknown"

    value = str(type_name).lower().strip()

    if value in {
        "int",
        "integer",
    }:
        return "int"

    if value in {
        "float",
        "double",
    }:
        return "float"

    if value in {
        "str",
        "string",
        "unicode",
    }:
        return "str"

    if value in {
        "bool",
        "boolean",
    }:
        return "bool"

    if value in {
        "list",
        "array",
    }:
        return "list"

    if value in {
        "tuple",
    }:
        return "tuple"

    if value in {
        "dict",
        "dictionary",
        "mapping",
    }:
        return "dict"

    if value in {
        "set",
    }:
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
    Produce conservative candidate values for a parameter type.

    These values are intentionally simple. They are candidates
    for differential testing, not assertions about what a
    function must accept.
    """

    parameter_type = normalize_type(type_name)

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
            None,
        ]

    # Unknown types are deliberately conservative.
    return [
        None,
    ]


def generate_no_argument_case(function_name):
    """
    Generate a test case for a function without parameters.
    """

    return TestCase(
        name="no_argument_case",
        function=function_name,
        inputs=[],
    )


def generate_single_parameter_cases(
    function_name,
    parameter,
):
    """
    Generate cases for one parameter.

    The generated cases vary only that parameter while the
    remaining parameters can be populated separately.
    """

    parameter_info = normalize_parameter(parameter)

    parameter_name = parameter_info["name"]
    parameter_type = parameter_info["type"]

    values = candidate_values(parameter_type)

    cases = []

    for index, value in enumerate(values):
        cases.append(
            TestCase(
                name=(
                    f"{parameter_name or 'parameter'}_case_"
                    f"{index + 1}"
                ),
                function=function_name,
                inputs=[value],
                expected_type=parameter_type,
            )
        )

    return cases


def generate_basic_cases(function_info):
    """
    Generate conservative behavioral test candidates.

    Args:
        function_info: Dictionary describing a function.

    Expected examples:

        {
            "name": "calculate_total",
            "parameters": ["amount"]
        }

    or:

        {
            "name": "calculate_total",
            "parameters": [
                {
                    "name": "amount",
                    "type": "float"
                }
            ]
        }

    Returns:
        list[TestCase]
    """

    function_name = function_info.get("name")
    parameters = function_info.get("parameters", [])

    if parameters is None:
        parameters = []

    # No parameters.
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

    # Generate one conservative case using the first
    # candidate value for every parameter.
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

    # Generate a positive/simple case for each parameter
    # while keeping other parameters conservative.
    for parameter_index, parameter in enumerate(
        normalized_parameters
    ):
        parameter_values = candidate_values(
            parameter["type"]
        )

        if not parameter_values:
            continue

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
                or f"parameter_{parameter_index + 1}"
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


def generate_cases_for_functions(functions):
    """
    Generate behavioral candidates for multiple discovered
    functions.

    Args:
        functions: Iterable of function metadata dictionaries.

    Returns:
        list[TestCase]
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
    Remove duplicate test cases while preserving order.
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