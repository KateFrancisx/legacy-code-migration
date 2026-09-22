import ast
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class CallableInfo:
    """
    Description of a callable discovered from Python source.
    """

    module_path: str
    qualified_name: str
    name: str
    callable_type: str
    class_name: str | None
    parameters: list
    line_number: int

    def to_dict(self):
        return asdict(self)


def _annotation_to_string(annotation):
    """
    Convert an AST annotation into a readable string.

    Returns None when the parameter has no annotation.
    """

    if annotation is None:
        return None

    try:
        return ast.unparse(annotation)
    except AttributeError:
        pass

    if isinstance(annotation, ast.Name):
        return annotation.id

    if isinstance(annotation, ast.Attribute):
        parts = []

        current = annotation

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        return ".".join(
            reversed(parts)
        )

    if isinstance(annotation, ast.Str):
        return annotation.s

    return None


def _parameter_info(parameter):
    """
    Convert an AST argument into generic parameter metadata.
    """

    annotation = getattr(
        parameter,
        "annotation",
        None,
    )

    return {
        "name": parameter.arg,
        "type": _annotation_to_string(
            annotation
        ),
    }


def _extract_parameters(node):
    """
    Extract function parameters.

    For instance methods, self/cls is excluded because it
    is supplied by the object instance rather than by the
    behavioral test input.
    """

    parameters = []

    arguments = node.args

    positional_only = getattr(
        arguments,
        "posonlyargs",
        [],
    )

    positional = (
        list(positional_only)
        + list(arguments.args)
    )

    defaults = list(
        arguments.defaults
    )

    default_start = (
        len(positional)
        - len(defaults)
    )

    for index, parameter in enumerate(
        positional
    ):
        info = _parameter_info(
            parameter
        )

        # self and cls are implicit method parameters.
        if info["name"] in {
            "self",
            "cls",
        }:
            continue

        info["has_default"] = (
            index >= default_start
        )

        parameters.append(
            info
        )

    vararg = arguments.vararg

    if vararg is not None:
        parameters.append(
            {
                "name": vararg.arg,
                "type": None,
                "has_default": False,
                "kind": "varargs",
            }
        )

    keyword_only = getattr(
        arguments,
        "kwonlyargs",
        [],
    )

    keyword_defaults = getattr(
        arguments,
        "kw_defaults",
        [],
    )

    for index, parameter in enumerate(
        keyword_only
    ):
        info = _parameter_info(
            parameter
        )

        info["has_default"] = (
            keyword_defaults[index]
            is not None
        )

        info["kind"] = "keyword_only"

        parameters.append(
            info
        )

    kwarg = arguments.kwarg

    if kwarg is not None:
        parameters.append(
            {
                "name": kwarg.arg,
                "type": None,
                "has_default": False,
                "kind": "kwargs",
            }
        )

    return parameters


def _discover_with_ast(
    source,
    module_path,
):
    """
    Discover functions and methods using Python AST.

    The AST parent relationship is tracked explicitly so
    module-level functions are never incorrectly classified
    as methods.
    """

    tree = ast.parse(
        source,
        filename=str(module_path),
    )

    discovered = []

    def visit_node(
        node,
        class_name=None,
    ):
        """
        Recursively visit the AST while carrying the current
        class context.
        """

        if isinstance(
            node,
            ast.ClassDef,
        ):
            # A class establishes the class context for its
            # immediate and nested definitions.
            for child in node.body:
                visit_node(
                    child,
                    class_name=node.name,
                )

            return

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            if class_name:
                qualified_name = (
                    class_name
                    + "."
                    + node.name
                )

                callable_type = "method"

            else:
                qualified_name = node.name
                callable_type = "function"

            discovered.append(
                CallableInfo(
                    module_path=str(
                        module_path
                    ),
                    qualified_name=qualified_name,
                    name=node.name,
                    callable_type=callable_type,
                    class_name=class_name,
                    parameters=_extract_parameters(
                        node
                    ),
                    line_number=getattr(
                        node,
                        "lineno",
                        0,
                    ),
                )
            )

            # Nested functions should be discovered as
            # functions rather than incorrectly inheriting
            # the surrounding class context.
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
                    visit_node(
                        child,
                        class_name=None,
                    )

            return

        for child in ast.iter_child_nodes(
            node
        ):
            visit_node(
                child,
                class_name=class_name,
            )

    for node in tree.body:
        visit_node(
            node,
            class_name=None,
        )

    return discovered


def _discover_legacy_fallback(
    source,
    module_path,
):
    """
    Conservative discovery fallback for legacy Python 2
    syntax that cannot be parsed by the current Python AST.

    The fallback tracks indentation so that module-level
    functions are not incorrectly classified as methods.
    """

    discovered = []

    current_class = None
    current_class_indent = None

    lines = source.splitlines()

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        if not line.strip():
            continue

        indentation = len(
            line
        ) - len(
            line.lstrip()
        )

        stripped = line.strip()

        # Leave a class when indentation returns to the
        # class's level or above.
        if (
            current_class is not None
            and current_class_indent is not None
            and indentation <= current_class_indent
            and not stripped.startswith(
                "class "
            )
        ):
            current_class = None
            current_class_indent = None

        if stripped.startswith(
            "class "
        ):
            class_part = stripped[
                len("class "):
            ]

            class_name = (
                class_part
                .split("(")[0]
                .split(":")[0]
                .strip()
            )

            current_class = (
                class_name
                or None
            )

            current_class_indent = (
                indentation
            )

            continue

        if stripped.startswith(
            "def "
        ):
            declaration = stripped[
                len("def "):
            ]

            name_part = declaration.split(
                "(",
                1,
            )

            function_name = (
                name_part[0].strip()
            )

            parameter_text = ""

            if len(name_part) > 1:
                parameter_text = (
                    name_part[1]
                    .split(")", 1)[0]
                )

            parameters = []

            raw_parameters = (
                parameter_text.split(",")
                if parameter_text
                else []
            )

            for raw_parameter in raw_parameters:
                raw_parameter = (
                    raw_parameter.strip()
                )

                if not raw_parameter:
                    continue

                if raw_parameter in {
                    "self",
                    "cls",
                }:
                    continue

                if raw_parameter.startswith(
                    "**"
                ):
                    parameters.append(
                        {
                            "name": raw_parameter[
                                2:
                            ].strip(),
                            "type": None,
                            "has_default": False,
                            "kind": "kwargs",
                        }
                    )

                    continue

                if raw_parameter.startswith(
                    "*"
                ):
                    parameters.append(
                        {
                            "name": raw_parameter[
                                1:
                            ].strip(),
                            "type": None,
                            "has_default": False,
                            "kind": "varargs",
                        }
                    )

                    continue

                parts = raw_parameter.split(
                    "=",
                    1,
                )

                parameter_name = (
                    parts[0].strip()
                )

                parameters.append(
                    {
                        "name": parameter_name,
                        "type": None,
                        "has_default": (
                            len(parts) > 1
                        ),
                    }
                )

            if current_class:
                qualified_name = (
                    current_class
                    + "."
                    + function_name
                )

                callable_type = "method"

            else:
                qualified_name = (
                    function_name
                )

                callable_type = "function"

            discovered.append(
                CallableInfo(
                    module_path=str(
                        module_path
                    ),
                    qualified_name=qualified_name,
                    name=function_name,
                    callable_type=callable_type,
                    class_name=current_class,
                    parameters=parameters,
                    line_number=line_number,
                )
            )

    return discovered


def discover_callables_from_source(
    source,
    module_path="<memory>",
):
    """
    Discover functions and methods from source code.

    AST parsing is preferred.

    If legacy syntax causes a SyntaxError, the conservative
    Python 2 fallback is used.
    """

    try:
        return _discover_with_ast(
            source,
            module_path,
        )

    except SyntaxError:
        return _discover_legacy_fallback(
            source,
            module_path,
        )


def discover_callables_in_file(
    file_path,
):
    """
    Discover functions and methods in one Python file.
    """

    file_path = Path(
        file_path
    )

    if not file_path.exists():
        raise FileNotFoundError(
            "Python file not found: "
            + str(file_path)
        )

    if not file_path.is_file():
        raise ValueError(
            "Expected a Python file: "
            + str(file_path)
        )

    source = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    return discover_callables_from_source(
        source,
        module_path=file_path,
    )


def discover_callables_in_repository(
    repository_path,
):
    """
    Discover functions and methods across an entire
    repository.
    """

    repository_path = Path(
        repository_path
    )

    if not repository_path.exists():
        raise FileNotFoundError(
            "Repository not found: "
            + str(repository_path)
        )

    if not repository_path.is_dir():
        raise ValueError(
            "Expected repository directory: "
            + str(repository_path)
        )

    results = []

    for file_path in sorted(
        repository_path.rglob("*.py")
    ):
        try:
            results.extend(
                discover_callables_in_file(
                    file_path
                )
            )

        except (
            OSError,
            UnicodeError,
        ):
            # One unreadable file should not stop repository
            # discovery.
            continue

    return results


def filter_test_files(
    callables,
):
    """
    Return callables belonging to likely test modules.
    """

    results = []

    for callable_info in callables:
        path = Path(
            callable_info.module_path
        )

        filename = path.name.lower()

        if (
            filename.startswith("test_")
            or filename.endswith("_test.py")
            or "tests" in path.parts
        ):
            results.append(
                callable_info
            )

    return results


def filter_non_test_callables(
    callables,
):
    """
    Return callables outside likely test modules.
    """

    test_ids = set(
        id(item)
        for item in filter_test_files(
            callables
        )
    )

    return [
        item
        for item in callables
        if id(item) not in test_ids
    ]