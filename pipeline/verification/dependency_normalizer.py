from dataclasses import dataclass, asdict


DEFAULT_IGNORED_CALLABLES = {
    # Python built-ins commonly encountered during analysis.
    "abs",
    "all",
    "any",
    "bool",
    "bytes",
    "callable",
    "dict",
    "dir",
    "enumerate",
    "filter",
    "float",
    "format",
    "getattr",
    "hasattr",
    "hash",
    "id",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "open",
    "ord",
    "pow",
    "print",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "super",
    "tuple",
    "type",
    "vars",
    "zip",

    # Python 2 runtime built-ins.
    "apply",
    "basestring",
    "cmp",
    "execfile",
    "file",
    "input",
    "long",
    "raw_input",
    "reduce",
    "unicode",
    "unichr",
    "xrange",
}


@dataclass
class NormalizedDependency:
    """
    Application-level behavioral dependency.

    The normalized representation removes obvious runtime
    implementation noise while preserving relationships that
    can help construct behavioral scenarios.
    """

    source: str
    target: str
    edge_type: str
    evidence: str

    def to_dict(self):
        return asdict(self)


def _edge_to_dict(edge):
    """
    Convert either a DependencyEdge or dictionary into a dictionary.
    """

    if hasattr(
        edge,
        "to_dict",
    ):
        return edge.to_dict()

    return edge


def _is_ignored_callable(
    name,
    ignored_callables,
):
    """
    Determine whether a callable is a runtime/built-in helper
    rather than an application-level dependency.
    """

    if not name:
        return False

    return name in ignored_callables


def _normalize_method_target(
    source,
    target,
    edge_type,
):
    """
    Normalize method calls so:

        Invoice.total -> subtotal

    becomes:

        Invoice.total -> Invoice.subtotal

    when the source identifies the containing class.

    The method target itself may still be unresolved if the source
    class is unavailable.
    """

    if edge_type != "method_to_callable":
        return target

    if "." not in source:
        return target

    class_name = source.rsplit(
        ".",
        1,
    )[0]

    if "." in target:
        return target

    return (
        class_name
        + "."
        + target
    )


def _normalize_callable_target(
    source,
    target,
):
    """
    Normalize a callable target using the source callable's class
    when possible.

    This does not attempt global symbol resolution.
    """

    if "." in target:
        return target

    if "." not in source:
        return target

    class_name = source.rsplit(
        ".",
        1,
    )[0]

    return (
        class_name
        + "."
        + target
    )


def _edge_key(edge):
    return (
        edge.source,
        edge.target,
        edge.edge_type,
    )


def normalize_dependencies(
    edges,
    ignored_callables=None,
):
    """
    Convert raw dependency edges into an application-level graph.

    The normalizer:

        1. removes obvious Python built-ins/runtime helpers
        2. removes duplicate relationships
        3. normalizes self-method targets
        4. preserves parameter/state relationships
        5. does not attempt speculative import resolution

    Args:
        edges:
            DependencyEdge objects or dictionaries.

        ignored_callables:
            Optional additional callable names to ignore.

    Returns:
        list[NormalizedDependency]
    """

    ignored = set(
        DEFAULT_IGNORED_CALLABLES
    )

    if ignored_callables:
        ignored.update(
            ignored_callables
        )

    normalized = []
    seen = set()

    for raw_edge in edges:
        edge = _edge_to_dict(
            raw_edge
        )

        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        edge_type = edge.get(
            "edge_type"
        )

        evidence = edge.get(
            "evidence",
            "",
        )

        # ----------------------------------------------------------
        # Ignore runtime/built-in call targets.
        # ----------------------------------------------------------

        if edge_type in {
            "parameter_to_callable",
            "callable_to_callable",
            "method_to_callable",
        }:
            if _is_ignored_callable(
                target,
                ignored,
            ):
                continue

        # ----------------------------------------------------------
        # Normalize method calls.
        # ----------------------------------------------------------

        if edge_type == "method_to_callable":
            target = _normalize_method_target(
                source,
                target,
                edge_type,
            )

        # ----------------------------------------------------------
        # Normalize ordinary callable relationships when the
        # source belongs to a class.
        #
        # Example:
        #
        # Invoice.total -> subtotal
        #
        # becomes:
        #
        # Invoice.total -> Invoice.subtotal
        # ----------------------------------------------------------

        if edge_type == "callable_to_callable":
            target = _normalize_callable_target(
                source,
                target,
            )

        normalized_edge = NormalizedDependency(
            source=source,
            target=target,
            edge_type=edge_type,
            evidence=evidence,
        )

        key = _edge_key(
            normalized_edge
        )

        if key in seen:
            continue

        seen.add(key)
        normalized.append(
            normalized_edge
        )

    return normalized


def filter_dependency_types(
    edges,
    allowed_types=None,
):
    """
    Keep only selected dependency types.

    Example:

        {
            "parameter_to_attribute",
            "attribute_to_method",
            "method_to_callable",
            "callable_to_callable",
        }
    """

    if allowed_types is None:
        return list(edges)

    allowed_types = set(
        allowed_types
    )

    result = []

    for edge in edges:
        edge_dict = _edge_to_dict(
            edge
        )

        if edge_dict.get(
            "edge_type"
        ) in allowed_types:
            result.append(
                edge
            )

    return result


def dependencies_for_callable(
    edges,
    callable_name,
):
    """
    Return dependencies directly associated with one callable.
    """

    result = []

    for edge in edges:
        edge_dict = _edge_to_dict(
            edge
        )

        if (
            edge_dict.get("source")
            == callable_name
            or edge_dict.get("target")
            == callable_name
        ):
            result.append(
                edge
            )

    return result


def dependencies_by_type(
    edges,
):
    """
    Group normalized dependencies by edge type.

    Returns:

        {
            "parameter_to_attribute": [...],
            "method_to_callable": [...],
            ...
        }
    """

    result = {}

    for edge in edges:
        edge_dict = _edge_to_dict(
            edge
        )

        edge_type = edge_dict.get(
            "edge_type"
        )

        result.setdefault(
            edge_type,
            [],
        ).append(
            edge
        )

    return result


def dependencies_to_dict(
    edges,
):
    """
    Convert normalized dependencies to JSON-friendly dictionaries.
    """

    return [
        _edge_to_dict(edge)
        for edge in edges
    ]


def summarize_dependencies(
    edges,
):
    """
    Produce simple graph statistics.
    """

    grouped = dependencies_by_type(
        edges
    )

    nodes = set()

    for edge in edges:
        edge_dict = _edge_to_dict(
            edge
        )

        nodes.add(
            edge_dict.get("source")
        )

        nodes.add(
            edge_dict.get("target")
        )

    nodes.discard(
        None
    )

    return {
        "total_edges": len(edges),
        "unique_nodes": len(nodes),
        "edge_types": {
            edge_type: len(
                values
            )
            for edge_type, values in grouped.items()
        },
    }