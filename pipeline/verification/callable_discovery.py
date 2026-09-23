import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CallableInfo:
    """
    Generic description of a callable discovered from Python source.

    A callable can be:

    - a module-level function
    - an instance method
    - a class method
    - a static method
    - a constructor

    The discovery process is repository-independent.
    """

    file_name: str
    qualified_name: str
    function_name: str
    kind: str
    class_name: str = None
    line: int = 0
    parameters: list = field(
        default_factory=list
    )

    def to_dict(self):
        """
        Convert the callable description into a JSON-friendly
        dictionary.
        """

        return {
            "file": self.file_name,
            "qualified_name": self.qualified_name,
            "function_name": self.function_name,
            "kind": self.kind,
            "class_name": self.class_name,
            "line": self.line,
            "parameters": self.parameters,
        }


def _parameter_names(function_node):
    """
    Extract parameter names from a function or method.

    Supports:

    - positional-only parameters
    - positional parameters
    - *args
    - keyword-only parameters
    - **kwargs
    """

    arguments = function_node.args

    parameters = []

    positional_only = getattr(
        arguments,
        "posonlyargs",
        [],
    )

    for argument in positional_only:
        parameters.append(
            argument.arg
        )

    for argument in arguments.args:
        parameters.append(
            argument.arg
        )

    if arguments.vararg is not None:
        parameters.append(
            "*" + arguments.vararg.arg
        )

    for argument in arguments.kwonlyargs:
        parameters.append(
            argument.arg
        )

    if arguments.kwarg is not None:
        parameters.append(
            "**" + arguments.kwarg.arg
        )

    return parameters


def _decorator_names(function_node):
    """
    Return simple decorator names.

    Examples:

        @staticmethod
        -> ["staticmethod"]

        @classmethod
        -> ["classmethod"]

        @foo.bar
        -> ["foo.bar"]
    """

    names = []

    for decorator in function_node.decorator_list:

        if isinstance(
            decorator,
            ast.Name,
        ):
            names.append(
                decorator.id
            )

        elif isinstance(
            decorator,
            ast.Attribute,
        ):
            parts = []

            current = decorator

            while isinstance(
                current,
                ast.Attribute,
            ):
                parts.append(
                    current.attr
                )
                current = current.value

            if isinstance(
                current,
                ast.Name,
            ):
                parts.append(
                    current.id
                )

            names.append(
                ".".join(
                    reversed(parts)
                )
            )

    return names


def _method_kind(function_node):
    """
    Determine the generic method category.
    """

    decorators = _decorator_names(
        function_node
    )

    if "staticmethod" in decorators:
        return "staticmethod"

    if "classmethod" in decorators:
        return "classmethod"

    if function_node.name == "__init__":
        return "constructor"

    return "instance_method"


class _CallableVisitor(ast.NodeVisitor):
    """
    Discover module-level functions, classes, and methods.

    Nested functions inside another function are not exposed
    as repository-level callables because they require the
    enclosing function's runtime scope.

    Nested classes are supported.
    """

    def __init__(self, file_name):
        self.file_name = file_name

        self.callables = []

        self.classes = []

        self._class_stack = []

        self._function_stack = []

    def visit_ClassDef(self, node):
        """
        Discover a class and its methods.
        """

        class_name = ".".join(
            self._class_stack + [node.name]
        )

        self.classes.append(
            {
                "file": self.file_name,
                "name": class_name,
                "line": node.lineno,
            }
        )

        self._class_stack.append(
            node.name
        )

        for child in node.body:

            if isinstance(
                child,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                self._record_method(
                    child
                )

            elif isinstance(
                child,
                ast.ClassDef,
            ):
                self.visit_ClassDef(
                    child
                )

        self._class_stack.pop()

    def visit_FunctionDef(self, node):
        """
        Discover a module-level function.
        """

        if self._class_stack:
            return

        if self._function_stack:
            return

        self._record_module_function(
            node
        )

    def visit_AsyncFunctionDef(self, node):
        """
        Discover an async module-level function.
        """

        if self._class_stack:
            return

        if self._function_stack:
            return

        self._record_module_function(
            node
        )

    def _record_module_function(
        self,
        node,
    ):
        self.callables.append(
            CallableInfo(
                file_name=self.file_name,
                qualified_name=node.name,
                function_name=node.name,
                kind="function",
                class_name=None,
                line=node.lineno,
                parameters=_parameter_names(
                    node
                ),
            )
        )

    def _record_method(
        self,
        node,
    ):
        class_name = ".".join(
            self._class_stack
        )

        qualified_name = (
            class_name
            + "."
            + node.name
        )

        self.callables.append(
            CallableInfo(
                file_name=self.file_name,
                qualified_name=qualified_name,
                function_name=node.name,
                kind=_method_kind(
                    node
                ),
                class_name=class_name,
                line=node.lineno,
                parameters=_parameter_names(
                    node
                ),
            )
        )


def discover_callables_from_source(
    source,
    file_name="<memory>",
):
    """
    Discover callable information from Python source text.

    The source must be parseable by the active Python
    interpreter.

    For legacy Python 2 repositories, callers should normally
    pass the migrated Python 3 source to this function.
    """

    tree = ast.parse(
        source,
        filename=file_name,
    )

    visitor = _CallableVisitor(
        file_name=file_name
    )

    visitor.visit(
        tree
    )

    return visitor.callables


def discover_callables_from_file(
    file_path,
    repository_root=None,
):
    """
    Discover callables from one Python source file.

    The file name in the resulting CallableInfo is relative
    to repository_root when repository_root is supplied.
    """

    file_path = Path(
        file_path
    ).resolve()

    if repository_root is not None:

        repository_root = Path(
            repository_root
        ).resolve()

        try:
            file_name = file_path.relative_to(
                repository_root
            ).as_posix()

        except ValueError:
            file_name = file_path.name

    else:
        file_name = file_path.name

    source = file_path.read_text(
        encoding="utf-8"
    )

    return discover_callables_from_source(
        source=source,
        file_name=file_name,
    )


def discover_callables(
    repository_path,
    file_names=None,
):
    """
    Discover Python callables across a repository.

    IMPORTANT:

    This function is intended to analyze Python source that
    can be parsed by the active Python interpreter.

    In a Python 2 -> Python 3 migration pipeline, the
    migrated repository should be supplied here because the
    migrated files are Python 3 source.

    The discovered callable names are then used to locate
    and execute the corresponding callable in the original
    repository under Python 2.

    If file_names is supplied, only those files are analyzed.

    If file_names is omitted, all Python files are analyzed.
    """

    repository_path = Path(
        repository_path
    ).resolve()

    if file_names is None:

        paths = sorted(
            repository_path.rglob(
                "*.py"
            )
        )

    else:

        paths = []

        for file_name in file_names:

            path = (
                repository_path
                / file_name
            )

            if path.exists():
                paths.append(
                    path
                )

    callables = []

    for path in paths:

        try:

            discovered = (
                discover_callables_from_file(
                    file_path=path,
                    repository_root=repository_path,
                )
            )

        except (
            SyntaxError,
            UnicodeDecodeError,
        ):
            # A legacy Python 2 source file may not be
            # parseable by Python 3.
            #
            # That is not a verification failure.
            # The migrated Python 3 source is the source
            # used for callable discovery.
            continue

        callables.extend(
            discovered
        )

    return callables


def callable_inventory(
    repository_path,
    file_names=None,
):
    """
    Return a JSON-friendly callable inventory grouped
    by file.
    """

    inventory = {}

    callables = discover_callables(
        repository_path=repository_path,
        file_names=file_names,
    )

    for callable_info in callables:

        inventory.setdefault(
            callable_info.file_name,
            [],
        ).append(
            callable_info.to_dict()
        )

    return inventory


def find_callable(
    repository_path,
    file_name,
    qualified_name,
):
    """
    Find one callable by its fully qualified name.

    Examples:

        build_invoice

        Invoice.total

        Outer.Inner.calculate
    """

    callables = discover_callables(
        repository_path=repository_path,
        file_names=[file_name],
    )

    for callable_info in callables:

        if (
            callable_info.qualified_name
            == qualified_name
        ):
            return callable_info

    return None