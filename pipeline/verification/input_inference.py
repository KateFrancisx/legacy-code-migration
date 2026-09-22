import ast
import re
from dataclasses import dataclass, asdict


@dataclass
class InputHint:
    parameter: str
    categories: list
    evidence: list

    def to_dict(self):
        return asdict(self)


def _unique(values):
    result = []
    seen = set()

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result


def _parameter_names(parameters):
    return {
        parameter.get("name")
        for parameter in parameters
        if parameter.get("name")
    }


def _direct_parameter(node, parameter_names):
    if isinstance(node, ast.Name):
        if node.id in parameter_names:
            return node.id

    return None


def _attribute_evidence(node, parameter_names):
    if not isinstance(node, ast.Attribute):
        return None

    parameter = _direct_parameter(
        node.value,
        parameter_names,
    )

    if parameter is None:
        return None

    method = node.attr

    string_methods = {
        "strip",
        "lstrip",
        "rstrip",
        "lower",
        "upper",
        "capitalize",
        "title",
        "replace",
        "split",
        "join",
        "startswith",
        "endswith",
        "find",
        "format",
    }

    collection_methods = {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "sort",
        "reverse",
    }

    if method in string_methods:
        return (
            parameter,
            "string-like",
            f"{parameter}.{method}()",
        )

    if method in collection_methods:
        return (
            parameter,
            "collection-like",
            f"{parameter}.{method}()",
        )

    return None


def _subscript_evidence(node, parameter_names):
    if not isinstance(node, ast.Subscript):
        return None

    parameter = _direct_parameter(
        node.value,
        parameter_names,
    )

    if parameter is None:
        return None

    slice_node = node.slice

    if isinstance(slice_node, ast.Constant):
        if isinstance(slice_node.value, str):
            return (
                parameter,
                "mapping-like",
                f"{parameter}[string-key]",
            )

        if isinstance(slice_node.value, int):
            return (
                parameter,
                "sequence-like",
                f"{parameter}[integer-index]",
            )

    if isinstance(slice_node, ast.Str):
        return (
            parameter,
            "mapping-like",
            f"{parameter}[string-key]",
        )

    if isinstance(slice_node, ast.Num):
        return (
            parameter,
            "sequence-like",
            f"{parameter}[integer-index]",
        )

    if isinstance(slice_node, ast.Slice):
        return (
            parameter,
            "sliceable",
            f"{parameter}[slice]",
        )

    return (
        parameter,
        "indexable",
        f"{parameter}[...]",
    )


def _binary_operation_evidence(node, parameter_names):
    if not isinstance(node, ast.BinOp):
        return []

    arithmetic_nodes = (
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
    )

    if not isinstance(node.op, arithmetic_nodes):
        return []

    results = []

    for operand in (
        node.left,
        node.right,
    ):
        parameter = _direct_parameter(
            operand,
            parameter_names,
        )

        if parameter is not None:
            category = "numeric-like"

            if isinstance(
                node.op,
                (
                    ast.FloorDiv,
                    ast.Mod,
                ),
            ):
                category = "integer-like"

            results.append(
                (
                    parameter,
                    category,
                    f"{parameter} used in arithmetic",
                )
            )

    return results


def _comparison_evidence(node, parameter_names):
    if not isinstance(node, ast.Compare):
        return []

    results = []

    operands = [
        node.left
    ] + list(
        node.comparators
    )

    for operand in operands:
        parameter = _direct_parameter(
            operand,
            parameter_names,
        )

        if parameter is not None:
            results.append(
                (
                    parameter,
                    "comparable",
                    f"{parameter} used in comparison",
                )
            )

    return results


def _len_evidence(node, parameter_names):
    if not isinstance(node, ast.Call):
        return None

    if not isinstance(node.func, ast.Name):
        return None

    if node.func.id != "len":
        return None

    if len(node.args) != 1:
        return None

    parameter = _direct_parameter(
        node.args[0],
        parameter_names,
    )

    if parameter is None:
        return None

    return (
        parameter,
        "sized",
        f"len({parameter})",
    )


def _iteration_evidence(node, parameter_names):
    if not isinstance(
        node,
        (
            ast.For,
            ast.AsyncFor,
        ),
    ):
        return None

    parameter = _direct_parameter(
        node.iter,
        parameter_names,
    )

    if parameter is None:
        return None

    return (
        parameter,
        "iterable-like",
        f"iteration over {parameter}",
    )


def _conversion_evidence(node, parameter_names):
    if not isinstance(node, ast.Call):
        return None

    if not isinstance(node.func, ast.Name):
        return None

    if not node.args:
        return None

    parameter = _direct_parameter(
        node.args[0],
        parameter_names,
    )

    if parameter is None:
        return None

    conversion_map = {
        "str": "string-convertible",
        "int": "integer-convertible",
        "float": "numeric-like",
        "bool": "boolean-convertible",
        "list": "collection-like",
        "tuple": "collection-like",
        "set": "collection-like",
        "dict": "mapping-like",
    }

    if node.func.id not in conversion_map:
        return None

    return (
        parameter,
        conversion_map[node.func.id],
        f"{node.func.id}({parameter})",
    )


def _builtin_evidence(node, parameter_names):
    if not isinstance(node, ast.Call):
        return None

    if not isinstance(node.func, ast.Name):
        return None

    if not node.args:
        return None

    parameter = _direct_parameter(
        node.args[0],
        parameter_names,
    )

    if parameter is None:
        return None

    builtin_map = {
        "sum": "numeric-iterable",
        "min": "comparable-iterable",
        "max": "comparable-iterable",
        "sorted": "orderable-iterable",
        "any": "iterable-like",
        "all": "iterable-like",
    }

    if node.func.id not in builtin_map:
        return None

    return (
        parameter,
        builtin_map[node.func.id],
        f"{node.func.id}({parameter})",
    )


def _call_argument_evidence(node, parameter_names):
    if not isinstance(node, ast.Call):
        return []

    results = []

    arguments = list(node.args)

    arguments.extend(
        keyword.value
        for keyword in node.keywords
        if keyword.value is not None
    )

    for argument in arguments:
        parameter = _direct_parameter(
            argument,
            parameter_names,
        )

        if parameter is not None:
            results.append(
                (
                    parameter,
                    "call-argument",
                    f"{parameter} passed to another callable",
                )
            )

    return results


def _formatting_evidence(node, parameter_names):
    results = []

    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Mod):
            operands = [
                node.left,
                node.right,
            ]

            for operand in operands:
                parameter = _direct_parameter(
                    operand,
                    parameter_names,
                )

                if parameter is not None:
                    results.append(
                        (
                            parameter,
                            "formatting-compatible",
                            f"{parameter} used in string formatting",
                        )
                    )

                if isinstance(
                    operand,
                    (
                        ast.Tuple,
                        ast.List,
                    ),
                ):
                    for element in operand.elts:
                        parameter = _direct_parameter(
                            element,
                            parameter_names,
                        )

                        if parameter is not None:
                            results.append(
                                (
                                    parameter,
                                    "formatting-compatible",
                                    f"{parameter} used in string formatting",
                                )
                            )

    if isinstance(node, ast.Call):
        if isinstance(
            node.func,
            ast.Attribute,
        ):
            if node.func.attr == "format":
                for argument in node.args:
                    parameter = _direct_parameter(
                        argument,
                        parameter_names,
                    )

                    if parameter is not None:
                        results.append(
                            (
                                parameter,
                                "formatting-compatible",
                                f"{parameter} passed to .format()",
                            )
                        )

    return results


def _merge_evidence(
    categories,
    evidence,
    result,
):
    if not result:
        return

    if isinstance(result, tuple):
        result = [result]

    for item in result:
        if len(item) != 3:
            continue

        parameter, category, reason = item

        if parameter not in categories:
            continue

        categories[parameter].append(
            category
        )

        evidence[parameter].append(
            reason
        )


def _find_callable_node(tree, callable_info):
    if hasattr(
        callable_info,
        "to_dict",
    ):
        callable_info = (
            callable_info.to_dict()
        )

    target_name = callable_info.get(
        "name"
    )

    target_class = callable_info.get(
        "class_name"
    )

    target_line = callable_info.get(
        "line_number",
        0,
    )

    candidates = []

    def visit(
        node,
        current_class=None,
    ):
        if isinstance(
            node,
            ast.ClassDef,
        ):
            for child in node.body:
                visit(
                    child,
                    current_class=node.name,
                )

            return

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            candidates.append(
                (
                    node,
                    current_class,
                )
            )

            for child in ast.iter_child_nodes(
                node
            ):
                if isinstance(
                    child,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):
                    visit(
                        child,
                        current_class=None,
                    )

            return

        for child in ast.iter_child_nodes(
            node
        ):
            visit(
                child,
                current_class=current_class,
            )

    for node in tree.body:
        visit(
            node,
            current_class=None,
        )

    for node, class_name in candidates:
        if (
            node.name == target_name
            and class_name == target_class
            and getattr(
                node,
                "lineno",
                0,
            ) == target_line
        ):
            return node

    for node, class_name in candidates:
        if (
            node.name == target_name
            and class_name == target_class
        ):
            return node

    for node, _ in candidates:
        if node.name == target_name:
            return node

    return None


def infer_inputs_from_callable_node(
    node,
    parameters,
):
    parameter_names = _parameter_names(
        parameters
    )

    categories = {
        name: []
        for name in parameter_names
    }

    evidence = {
        name: []
        for name in parameter_names
    }

    for child in ast.walk(node):

        _merge_evidence(
            categories,
            evidence,
            _attribute_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _subscript_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _binary_operation_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _comparison_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _len_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _iteration_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _conversion_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _builtin_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _call_argument_evidence(
                child,
                parameter_names,
            ),
        )

        _merge_evidence(
            categories,
            evidence,
            _formatting_evidence(
                child,
                parameter_names,
            ),
        )

    return {
        parameter: InputHint(
            parameter=parameter,
            categories=_unique(
                categories[parameter]
            ),
            evidence=_unique(
                evidence[parameter]
            ),
        )
        for parameter in parameter_names
    }


# ----------------------------------------------------------------------
# Python 2 fallback
# ----------------------------------------------------------------------


def _strip_inline_comment(line):
    in_single = False
    in_double = False
    escaped = False

    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == "'" and not in_double:
            in_single = not in_single
            continue

        if character == '"' and not in_single:
            in_double = not in_double
            continue

        if (
            character == "#"
            and not in_single
            and not in_double
        ):
            return line[:index]

    return line


def _parameter_regex(parameter):
    return re.escape(parameter)


def _legacy_parameter_evidence(
    body,
    parameters,
    attribute_aliases=None,
):
    """
    Infer input categories from Python 2 source.

    attribute_aliases maps instance attributes back to their
    originating constructor parameters.

    Example:

        self.items = items

    produces:

        {"items": ["items"]}

    allowing later uses such as:

        for item in self.items
        self.items[0]
    """

    parameter_names = _parameter_names(
        parameters
    )

    categories = {
        name: []
        for name in parameter_names
    }

    evidence = {
        name: []
        for name in parameter_names
    }

    attribute_aliases = (
        attribute_aliases
        or {}
    )

    # --------------------------------------------------------------
    # First pass: discover parameter -> self.attribute relationships.
    # --------------------------------------------------------------

    assignment_pattern = re.compile(
        r"\bself\.(\w+)\s*=\s*"
        r"([A-Za-z_]\w*)\b"
    )

    for line in body.splitlines():
        line = _strip_inline_comment(
            line
        )

        for match in assignment_pattern.finditer(
            line
        ):
            attribute = match.group(1)
            value = match.group(2)

            if value in parameter_names:
                attribute_aliases[
                    attribute
                ] = value

                categories[value].append(
                    "stored-as-attribute"
                )

                evidence[value].append(
                    f"{value} stored as self.{attribute}"
                )

    # --------------------------------------------------------------
    # Second pass: analyze direct parameter usage and aliased
    # instance-attribute usage.
    # --------------------------------------------------------------

    for raw_line in body.splitlines():
        line = _strip_inline_comment(
            raw_line
        ).strip()

        if not line:
            continue

        for parameter in parameter_names:
            escaped = _parameter_regex(
                parameter
            )

            # ------------------------------------------------------
            # Direct string-like operations.
            # ------------------------------------------------------

            string_methods = (
                "strip",
                "lstrip",
                "rstrip",
                "lower",
                "upper",
                "capitalize",
                "title",
                "replace",
                "split",
                "startswith",
                "endswith",
                "find",
            )

            for method in string_methods:
                pattern = (
                    rf"\b{escaped}\s*\.\s*"
                    rf"{method}\s*\("
                )

                if re.search(
                    pattern,
                    line,
                ):
                    categories[parameter].append(
                        "string-like"
                    )

                    evidence[parameter].append(
                        f"{parameter}.{method}()"
                    )

            # ------------------------------------------------------
            # Direct mapping access.
            # ------------------------------------------------------

            mapping_pattern = (
                rf"\b{escaped}\s*\[\s*"
                rf"['\"]"
            )

            if re.search(
                mapping_pattern,
                line,
            ):
                categories[parameter].append(
                    "mapping-like"
                )

                evidence[parameter].append(
                    f"{parameter}[string-key]"
                )

            # ------------------------------------------------------
            # Direct sequence access.
            # ------------------------------------------------------

            index_pattern = (
                rf"\b{escaped}\s*\[\s*"
                rf"-?\d+\s*\]"
            )

            if re.search(
                index_pattern,
                line,
            ):
                categories[parameter].append(
                    "sequence-like"
                )

                evidence[parameter].append(
                    f"{parameter}[integer-index]"
                )

            # ------------------------------------------------------
            # Direct slicing.
            # ------------------------------------------------------

            slice_pattern = (
                rf"\b{escaped}\s*\[\s*"
                rf"[^]]*:[^]]*\]"
            )

            if re.search(
                slice_pattern,
                line,
            ):
                categories[parameter].append(
                    "sliceable"
                )

                evidence[parameter].append(
                    f"{parameter}[slice]"
                )

            # ------------------------------------------------------
            # len(parameter)
            # ------------------------------------------------------

            if re.search(
                rf"\blen\s*\(\s*{escaped}\s*\)",
                line,
            ):
                categories[parameter].append(
                    "sized"
                )

                evidence[parameter].append(
                    f"len({parameter})"
                )

            # ------------------------------------------------------
            # Iteration.
            # ------------------------------------------------------

            if re.search(
                rf"\bfor\s+\w+\s+in\s+{escaped}\b",
                line,
            ):
                categories[parameter].append(
                    "iterable-like"
                )

                evidence[parameter].append(
                    f"iteration over {parameter}"
                )

            # ------------------------------------------------------
            # Arithmetic.
            # ------------------------------------------------------

            arithmetic_pattern = (
                rf"\b{escaped}\b\s*"
                rf"(?:\+|-|\*|/|//|%)"
            )

            reverse_arithmetic_pattern = (
                rf"(?:\+|-|\*|/|//|%)\s*"
                rf"\b{escaped}\b"
            )

            if (
                re.search(
                    arithmetic_pattern,
                    line,
                )
                or re.search(
                    reverse_arithmetic_pattern,
                    line,
                )
            ):
                categories[parameter].append(
                    "numeric-like"
                )

                evidence[parameter].append(
                    f"{parameter} used in arithmetic"
                )

            # ------------------------------------------------------
            # Comparisons.
            # ------------------------------------------------------

            comparison_pattern = (
                rf"\b{escaped}\b\s*"
                rf"(?:==|!=|<=|>=|<|>)"
            )

            reverse_comparison_pattern = (
                rf"(?:==|!=|<=|>=|<|>)\s*"
                rf"\b{escaped}\b"
            )

            if (
                re.search(
                    comparison_pattern,
                    line,
                )
                or re.search(
                    reverse_comparison_pattern,
                    line,
                )
            ):
                categories[parameter].append(
                    "comparable"
                )

                evidence[parameter].append(
                    f"{parameter} used in comparison"
                )

            # ------------------------------------------------------
            # Conversions.
            # ------------------------------------------------------

            conversions = {
                "str": "string-convertible",
                "int": "integer-convertible",
                "float": "numeric-like",
                "bool": "boolean-convertible",
                "list": "collection-like",
                "tuple": "collection-like",
                "set": "collection-like",
                "dict": "mapping-like",
            }

            for function_name, category in (
                conversions.items()
            ):
                conversion_pattern = (
                    rf"\b{function_name}\s*\(\s*"
                    rf"{escaped}\s*\)"
                )

                if re.search(
                    conversion_pattern,
                    line,
                ):
                    categories[parameter].append(
                        category
                    )

                    evidence[parameter].append(
                        f"{function_name}({parameter})"
                    )

            # ------------------------------------------------------
            # Formatting.
            # ------------------------------------------------------

            formatting_patterns = [
                rf"%\s*{escaped}\b",
                rf"\b{escaped}\b\s*%",
                rf"\bformat\s*\(\s*{escaped}\s*\)",
            ]

            for pattern in formatting_patterns:
                if re.search(
                    pattern,
                    line,
                ):
                    categories[parameter].append(
                        "formatting-compatible"
                    )

                    evidence[parameter].append(
                        f"{parameter} used in string formatting"
                    )

            # ------------------------------------------------------
            # Direct call-argument usage.
            # ------------------------------------------------------

            call_argument_pattern = (
                rf"\b\w+\s*\([^)]*\b"
                rf"{escaped}\b[^)]*\)"
            )

            if re.search(
                call_argument_pattern,
                line,
            ):
                categories[parameter].append(
                    "call-argument"
                )

                evidence[parameter].append(
                    f"{parameter} passed to another callable"
                )

            # ------------------------------------------------------
            # Analyze every self.attribute that maps back to this
            # parameter.
            # ------------------------------------------------------

            for attribute, origin_parameter in (
                attribute_aliases.items()
            ):
                if origin_parameter != parameter:
                    continue

                attribute_expression = (
                    rf"\bself\.{re.escape(attribute)}\b"
                )

                # self.items["price"]
                if re.search(
                    attribute_expression
                    + r"\s*\[\s*['\"]",
                    line,
                ):
                    categories[parameter].append(
                        "mapping-like"
                    )

                    evidence[parameter].append(
                        f"self.{attribute}[string-key]"
                    )

                # self.items[0]
                if re.search(
                    attribute_expression
                    + r"\s*\[\s*-?\d+\s*\]",
                    line,
                ):
                    categories[parameter].append(
                        "sequence-like"
                    )

                    evidence[parameter].append(
                        f"self.{attribute}[integer-index]"
                    )

                # self.items[start:end]
                if re.search(
                    attribute_expression
                    + r"\s*\[[^]]*:[^]]*\]",
                    line,
                ):
                    categories[parameter].append(
                        "sliceable"
                    )

                    evidence[parameter].append(
                        f"self.{attribute}[slice]"
                    )

                # len(self.items)
                if re.search(
                    rf"\blen\s*\(\s*"
                    + attribute_expression
                    + r"\s*\)",
                    line,
                ):
                    categories[parameter].append(
                        "sized"
                    )

                    evidence[parameter].append(
                        f"len(self.{attribute})"
                    )

                # for x in self.items
                if re.search(
                    rf"\bfor\s+\w+\s+in\s+"
                    + attribute_expression
                    + r"\b",
                    line,
                ):
                    categories[parameter].append(
                        "iterable-like"
                    )

                    evidence[parameter].append(
                        f"iteration over self.{attribute}"
                    )

                # self.items.append(...)
                if re.search(
                    attribute_expression
                    + r"\s*\.\s*"
                    r"(?:append|extend|insert|remove|pop|sort|reverse)"
                    r"\s*\(",
                    line,
                ):
                    categories[parameter].append(
                        "collection-like"
                    )

                    evidence[parameter].append(
                        f"self.{attribute} used as collection"
                    )

                # self.name.strip()
                if re.search(
                    attribute_expression
                    + r"\s*\.\s*"
                    r"(?:strip|lower|upper|replace|split)"
                    r"\s*\(",
                    line,
                ):
                    categories[parameter].append(
                        "string-like"
                    )

                    evidence[parameter].append(
                        f"self.{attribute} used as string"
                    )

    return {
        parameter: InputHint(
            parameter=parameter,
            categories=_unique(
                categories[parameter]
            ),
            evidence=_unique(
                evidence[parameter]
            ),
        )
        for parameter in parameter_names
    }


def _extract_legacy_callable_body(
    source,
    callable_info,
):
    """
    Extract the approximate body of a Python 2 callable.

    The callable's discovered line number determines the start.
    The indentation level determines where the callable ends.
    """

    if hasattr(
        callable_info,
        "to_dict",
    ):
        callable_info = (
            callable_info.to_dict()
        )

    target_line = callable_info.get(
        "line_number",
        0,
    )

    lines = source.splitlines()

    if target_line <= 0 or target_line > len(lines):
        return ""

    start_index = target_line - 1

    declaration = lines[start_index]

    base_indent = (
        len(declaration)
        - len(declaration.lstrip())
    )

    body_lines = []

    for line in lines[
        start_index + 1:
    ]:
        if not line.strip():
            body_lines.append(line)
            continue

        indentation = (
            len(line)
            - len(line.lstrip())
        )

        stripped = line.strip()

        if (
            indentation <= base_indent
            and (
                stripped.startswith("def ")
                or stripped.startswith("class ")
            )
        ):
            break

        body_lines.append(line)

    return "\n".join(
        body_lines
    )


def _find_constructor_attribute_aliases(
    source,
    callable_info,
):
    """
    Find instance attributes initialized from constructor
    parameters.

    This is intentionally conservative and only recognizes
    direct assignments such as:

        self.items = items
        self.customer_name = customer_name
    """

    if hasattr(
        callable_info,
        "to_dict",
    ):
        callable_info = (
            callable_info.to_dict()
        )

    if callable_info.get(
        "name"
    ) != "__init__":
        return {}

    parameters = (
        callable_info.get(
            "parameters",
            [],
        )
        or []
    )

    parameter_names = _parameter_names(
        parameters
    )

    body = _extract_legacy_callable_body(
        source,
        callable_info,
    )

    aliases = {}

    pattern = re.compile(
        r"\bself\.(\w+)\s*=\s*"
        r"([A-Za-z_]\w*)\b"
    )

    for line in body.splitlines():
        line = _strip_inline_comment(
            line
        )

        for match in pattern.finditer(
            line
        ):
            attribute = match.group(1)
            parameter = match.group(2)

            if parameter in parameter_names:
                aliases[attribute] = parameter

    return aliases


def infer_inputs_from_legacy_source(
    source,
    parameters,
    callable_info,
):
    """
    Perform conservative Python 2 inference with instance-state
    tracking.
    """

    aliases = _find_constructor_attribute_aliases(
        source,
        callable_info,
    )

    body = _extract_legacy_callable_body(
        source,
        callable_info,
    )

    return _legacy_parameter_evidence(
        body,
        parameters,
        attribute_aliases=aliases,
    )


def infer_inputs_from_source(
    source,
    parameters,
    callable_info=None,
):
    """
    Infer inputs from source.

    Modern Python-compatible source uses AST analysis.

    Python 2 syntax uses the conservative legacy fallback.
    """

    try:
        tree = ast.parse(source)

    except SyntaxError:
        if callable_info is not None:
            return infer_inputs_from_legacy_source(
                source,
                parameters,
                callable_info,
            )

        return {
            parameter["name"]: InputHint(
                parameter=parameter["name"],
                categories=[],
                evidence=[
                    "Source could not be parsed and no "
                    "callable context was supplied."
                ],
            )
            for parameter in parameters
            if parameter.get("name")
        }

    if callable_info is None:
        return infer_inputs_from_callable_node(
            tree,
            parameters,
        )

    node = _find_callable_node(
        tree,
        callable_info,
    )

    if node is None:
        return {
            parameter["name"]: InputHint(
                parameter=parameter["name"],
                categories=[],
                evidence=[
                    "Callable AST node could not be located."
                ],
            )
            for parameter in parameters
            if parameter.get("name")
        }

    return infer_inputs_from_callable_node(
        node,
        parameters,
    )


def infer_inputs_for_callable(
    source,
    callable_info,
):
    """
    Infer parameter usage for exactly one discovered callable.
    """

    if hasattr(
        callable_info,
        "to_dict",
    ):
        callable_dict = (
            callable_info.to_dict()
        )
    else:
        callable_dict = callable_info

    parameters = (
        callable_dict.get(
            "parameters",
            [],
        )
        or []
    )

    return infer_inputs_from_source(
        source,
        parameters,
        callable_info=callable_dict,
    )


def hints_to_dict(hints):
    """
    Convert InputHint objects into JSON-friendly dictionaries.
    """

    return {
        name: hint.to_dict()
        for name, hint in hints.items()
    }