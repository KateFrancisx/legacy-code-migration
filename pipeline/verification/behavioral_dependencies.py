import ast
import re
from dataclasses import dataclass, asdict


@dataclass
class DependencyEdge:
    """
    A behavioral dependency between two entities.

    edge_type examples:
        parameter_to_callable
        parameter_to_attribute
        attribute_to_method
        method_to_callable
        callable_to_callable
    """

    source: str
    target: str
    edge_type: str
    evidence: str

    def to_dict(self):
        return asdict(self)


def _unique_edges(edges):
    """
    Remove duplicate dependency edges while preserving order.
    """

    result = []
    seen = set()

    for edge in edges:
        key = (
            edge.source,
            edge.target,
            edge.edge_type,
            edge.evidence,
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(edge)

    return result


def _parameter_names(callable_info):
    """
    Return the explicit parameter names for a callable.
    """

    if hasattr(callable_info, "to_dict"):
        callable_info = callable_info.to_dict()

    return {
        parameter.get("name")
        for parameter in (
            callable_info.get("parameters", [])
            or []
        )
        if parameter.get("name")
    }


def _callable_identifier(callable_info):
    """
    Return the qualified callable name.
    """

    if hasattr(callable_info, "to_dict"):
        callable_info = callable_info.to_dict()

    return callable_info.get(
        "qualified_name"
    ) or callable_info.get(
        "name"
    )


def _class_name(callable_info):
    """
    Return the containing class name, if any.
    """

    if hasattr(callable_info, "to_dict"):
        callable_info = callable_info.to_dict()

    return callable_info.get(
        "class_name"
    )


def _direct_parameter(node, parameter_names):
    """
    Return a parameter name when node directly references it.
    """

    if isinstance(node, ast.Name):
        if node.id in parameter_names:
            return node.id

    return None


def _attribute_name(node):
    """
    Return an attribute name for:

        self.items

    or:

        object.items

    """

    if not isinstance(
        node,
        ast.Attribute,
    ):
        return None

    return node.attr


def _find_callable_node(
    tree,
    callable_info,
):
    """
    Locate the AST node corresponding to one callable.
    """

    if hasattr(
        callable_info,
        "to_dict",
    ):
        callable_info = callable_info.to_dict()

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


def _parameter_to_callable_edges(
    node,
    callable_info,
):
    """
    Detect parameters passed to other callables.

    Example:

        normalize_name(customer_name)

    produces:

        customer_name -> normalize_name
    """

    parameter_names = _parameter_names(
        callable_info
    )

    edges = []

    for child in ast.walk(node):
        if not isinstance(
            child,
            ast.Call,
        ):
            continue

        if isinstance(
            child.func,
            ast.Name,
        ):
            target = child.func.id

        elif isinstance(
            child.func,
            ast.Attribute,
        ):
            target = child.func.attr

        else:
            continue

        arguments = list(
            child.args
        )

        arguments.extend(
            keyword.value
            for keyword in child.keywords
            if keyword.value is not None
        )

        for argument in arguments:
            parameter = _direct_parameter(
                argument,
                parameter_names,
            )

            if parameter is None:
                continue

            edges.append(
                DependencyEdge(
                    source=parameter,
                    target=target,
                    edge_type="parameter_to_callable",
                    evidence=(
                        f"{parameter} passed to "
                        f"{target}()"
                    ),
                )
            )

    return edges


def _parameter_to_attribute_edges(
    node,
    callable_info,
):
    """
    Detect direct assignments such as:

        self.items = items

    producing:

        items -> self.items
    """

    parameter_names = _parameter_names(
        callable_info
    )

    edges = []

    for child in ast.walk(node):
        if not isinstance(
            child,
            ast.Assign,
        ):
            continue

        value_parameter = _direct_parameter(
            child.value,
            parameter_names,
        )

        if value_parameter is None:
            continue

        for target in child.targets:
            if not isinstance(
                target,
                ast.Attribute,
            ):
                continue

            if not isinstance(
                target.value,
                ast.Name,
            ):
                continue

            if target.value.id != "self":
                continue

            attribute = target.attr

            edges.append(
                DependencyEdge(
                    source=value_parameter,
                    target=f"self.{attribute}",
                    edge_type="parameter_to_attribute",
                    evidence=(
                        f"{value_parameter} assigned to "
                        f"self.{attribute}"
                    ),
                )
            )

    return edges


def _attribute_to_method_edges(
    node,
    callable_info,
):
    """
    Detect instance-state usage such as:

        self.items
        self.customer_name.strip()

    This creates an attribute-to-method relationship.
    """

    class_name = _class_name(
        callable_info
    )

    callable_name = _callable_identifier(
        callable_info
    )

    edges = []

    if not class_name:
        return edges

    for child in ast.walk(node):
        if isinstance(
            child,
            ast.Attribute,
        ):
            if isinstance(
                child.value,
                ast.Name,
            ):
                if child.value.id == "self":
                    edges.append(
                        DependencyEdge(
                            source=f"self.{child.attr}",
                            target=callable_name,
                            edge_type="attribute_to_method",
                            evidence=(
                                f"{callable_name} uses "
                                f"self.{child.attr}"
                            ),
                        )
                    )

    return edges


def _method_to_callable_edges(
    node,
    callable_info,
):
    """
    Detect calls such as:

        self.subtotal()
        self.discount()

    producing:

        Invoice.total -> subtotal
        Invoice.total -> discount
    """

    callable_name = _callable_identifier(
        callable_info
    )

    edges = []

    for child in ast.walk(node):
        if not isinstance(
            child,
            ast.Call,
        ):
            continue

        if not isinstance(
            child.func,
            ast.Attribute,
        ):
            continue

        if not isinstance(
            child.func.value,
            ast.Name,
        ):
            continue

        if child.func.value.id != "self":
            continue

        target = child.func.attr

        edges.append(
            DependencyEdge(
                source=callable_name,
                target=target,
                edge_type="method_to_callable",
                evidence=(
                    f"{callable_name} calls "
                    f"self.{target}()"
                ),
            )
        )

    return edges


def _callable_to_callable_edges(
    node,
    callable_info,
):
    """
    Detect ordinary function calls.

    This records callable-level relationships without
    attempting to resolve imports yet.
    """

    callable_name = _callable_identifier(
        callable_info
    )

    edges = []

    for child in ast.walk(node):
        if not isinstance(
            child,
            ast.Call,
        ):
            continue

        if isinstance(
            child.func,
            ast.Name,
        ):
            target = child.func.id

            edges.append(
                DependencyEdge(
                    source=callable_name,
                    target=target,
                    edge_type="callable_to_callable",
                    evidence=(
                        f"{callable_name} calls "
                        f"{target}()"
                    ),
                )
            )

    return edges


def analyze_callable_dependencies(
    source,
    callable_info,
):
    """
    Analyze one Python 3-compatible callable.

    Returns a list of DependencyEdge objects.

    Python 2 source that cannot be parsed by the current
    AST parser is handled by the conservative textual
    fallback.
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

    try:
        tree = ast.parse(
            source
        )

    except SyntaxError:
        return analyze_legacy_callable_dependencies(
            source,
            callable_dict,
        )

    node = _find_callable_node(
        tree,
        callable_dict,
    )

    if node is None:
        return []

    edges = []

    edges.extend(
        _parameter_to_callable_edges(
            node,
            callable_dict,
        )
    )

    edges.extend(
        _parameter_to_attribute_edges(
            node,
            callable_dict,
        )
    )

    edges.extend(
        _attribute_to_method_edges(
            node,
            callable_dict,
        )
    )

    edges.extend(
        _method_to_callable_edges(
            node,
            callable_dict,
        )
    )

    edges.extend(
        _callable_to_callable_edges(
            node,
            callable_dict,
        )
    )

    return _unique_edges(
        edges
    )


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


def _extract_legacy_callable_body(
    source,
    callable_info,
):
    """
    Extract the approximate body of a legacy callable using
    its discovered line number and indentation.
    """

    target_line = callable_info.get(
        "line_number",
        0,
    )

    lines = source.splitlines()

    if (
        target_line <= 0
        or target_line > len(lines)
    ):
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


def _legacy_parameter_to_callable_edges(
    body,
    callable_info,
):
    """
    Detect parameter values passed to callables.
    """

    parameter_names = _parameter_names(
        callable_info
    )

    edges = []

    for raw_line in body.splitlines():
        line = _strip_inline_comment(
            raw_line
        ).strip()

        if not line:
            continue

        for parameter in parameter_names:
            pattern = (
                rf"\b([A-Za-z_]\w*)\s*"
                rf"\([^)]*\b"
                rf"{re.escape(parameter)}\b"
                rf"[^)]*\)"
            )

            for match in re.finditer(
                pattern,
                line,
            ):
                target = match.group(1)

                edges.append(
                    DependencyEdge(
                        source=parameter,
                        target=target,
                        edge_type="parameter_to_callable",
                        evidence=(
                            f"{parameter} passed to "
                            f"{target}()"
                        ),
                    )
                )

    return edges


def _legacy_parameter_to_attribute_edges(
    body,
    callable_info,
):
    """
    Detect:

        self.attribute = parameter
    """

    parameter_names = _parameter_names(
        callable_info
    )

    edges = []

    pattern = re.compile(
        r"\bself\.(\w+)\s*=\s*"
        r"([A-Za-z_]\w*)\b"
    )

    for raw_line in body.splitlines():
        line = _strip_inline_comment(
            raw_line
        )

        for match in pattern.finditer(
            line
        ):
            attribute = match.group(1)
            parameter = match.group(2)

            if parameter not in parameter_names:
                continue

            edges.append(
                DependencyEdge(
                    source=parameter,
                    target=f"self.{attribute}",
                    edge_type="parameter_to_attribute",
                    evidence=(
                        f"{parameter} assigned to "
                        f"self.{attribute}"
                    ),
                )
            )

    return edges


def _legacy_attribute_to_method_edges(
    body,
    callable_info,
):
    """
    Detect uses of self.attribute inside a method.
    """

    callable_name = _callable_identifier(
        callable_info
    )

    edges = []

    pattern = re.compile(
        r"\bself\.(\w+)\b"
    )

    for raw_line in body.splitlines():
        line = _strip_inline_comment(
            raw_line
        ).strip()

        if not line:
            continue

        for match in pattern.finditer(
            line
        ):
            attribute = match.group(1)

            edges.append(
                DependencyEdge(
                    source=f"self.{attribute}",
                    target=callable_name,
                    edge_type="attribute_to_method",
                    evidence=(
                        f"{callable_name} uses "
                        f"self.{attribute}"
                    ),
                )
            )

    return edges


def _legacy_method_to_callable_edges(
    body,
    callable_info,
):
    """
    Detect:

        self.subtotal()
        self.discount()
    """

    callable_name = _callable_identifier(
        callable_info
    )

    edges = []

    pattern = re.compile(
        r"\bself\.(\w+)\s*\("
    )

    for raw_line in body.splitlines():
        line = _strip_inline_comment(
            raw_line
        ).strip()

        for match in pattern.finditer(
            line
        ):
            target = match.group(1)

            edges.append(
                DependencyEdge(
                    source=callable_name,
                    target=target,
                    edge_type="method_to_callable",
                    evidence=(
                        f"{callable_name} calls "
                        f"self.{target}()"
                    ),
                )
            )

    return edges


def _legacy_callable_to_callable_edges(
    body,
    callable_info,
):
    """
    Detect ordinary function calls in legacy source.

    Built-ins and obvious control keywords are excluded.
    """

    callable_name = _callable_identifier(
        callable_info
    )

    excluded = {
        "if",
        "for",
        "while",
        "return",
        "print",
        "range",
        "len",
        "sum",
        "min",
        "max",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "tuple",
        "set",
    }

    edges = []

    pattern = re.compile(
        r"\b([A-Za-z_]\w*)\s*\("
    )

    for raw_line in body.splitlines():
        line = _strip_inline_comment(
            raw_line
        ).strip()

        for match in pattern.finditer(
            line
        ):
            target = match.group(1)

            if target in excluded:
                continue

            if target == callable_name:
                continue

            edges.append(
                DependencyEdge(
                    source=callable_name,
                    target=target,
                    edge_type="callable_to_callable",
                    evidence=(
                        f"{callable_name} calls "
                        f"{target}()"
                    ),
                )
            )

    return edges


def analyze_legacy_callable_dependencies(
    source,
    callable_info,
):
    """
    Analyze a Python 2 callable using conservative textual
    patterns.
    """

    body = _extract_legacy_callable_body(
        source,
        callable_info,
    )

    edges = []

    edges.extend(
        _legacy_parameter_to_callable_edges(
            body,
            callable_info,
        )
    )

    edges.extend(
        _legacy_parameter_to_attribute_edges(
            body,
            callable_info,
        )
    )

    edges.extend(
        _legacy_attribute_to_method_edges(
            body,
            callable_info,
        )
    )

    edges.extend(
        _legacy_method_to_callable_edges(
            body,
            callable_info,
        )
    )

    edges.extend(
        _legacy_callable_to_callable_edges(
            body,
            callable_info,
        )
    )

    return _unique_edges(
        edges
    )


def analyze_repository_dependencies(
    repository_path,
    callables,
):
    """
    Analyze behavioral dependencies across all supplied
    callables in a repository.

    Args:
        repository_path: repository root path.
        callables: discovered CallableInfo objects.

    Returns:
        list[DependencyEdge]
    """

    from pathlib import Path

    repository_path = Path(
        repository_path
    )

    source_cache = {}

    edges = []

    for callable_info in callables:
        if hasattr(
            callable_info,
            "to_dict",
        ):
            callable_dict = (
                callable_info.to_dict()
            )
        else:
            callable_dict = callable_info

        module_path = Path(
            callable_dict["module_path"]
        )

        if module_path not in source_cache:
            try:
                source_cache[
                    module_path
                ] = module_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except OSError:
                source_cache[
                    module_path
                ] = ""

        source = source_cache[
            module_path
        ]

        edges.extend(
            analyze_callable_dependencies(
                source,
                callable_dict,
            )
        )

    return _unique_edges(
        edges
    )


def dependencies_to_dict(edges):
    """
    Convert dependency edges to JSON-friendly dictionaries.
    """

    return [
        edge.to_dict()
        if hasattr(
            edge,
            "to_dict",
        )
        else edge
        for edge in edges
    ]