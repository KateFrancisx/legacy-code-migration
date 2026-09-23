import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass
class FunctionExecutionResult:
    status: str
    return_value: object = None
    return_type: str = None
    stdout: str = ""
    stderr: str = ""
    exception_type: str = None
    exception_message: str = None
    timed_out: bool = False


def _normalize_python_command(
    python_executable
):
    if isinstance(
        python_executable,
        (list, tuple),
    ):
        return [
            str(part)
            for part in python_executable
        ]

    if not python_executable:
        return [
            "python"
        ]

    return shlex.split(
        str(
            python_executable
        ),
        posix=False,
    )


def _build_runner_script(
    repository_root,
    target_module_path,
    target_function_name,
    function_inputs,
    target_class_name=None,
    callable_kind="function",
    constructor_inputs=None,
):
    payload = {
        "repository_root": repository_root,
        "target_module_path": target_module_path,
        "target_function_name": target_function_name,
        "function_inputs": function_inputs,
        "target_class_name": target_class_name,
        "callable_kind": callable_kind,
        "constructor_inputs": constructor_inputs,
    }

    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
    )

    runner_template = r'''
import json
import os
import sys


PAYLOAD = json.loads(
    __PAYLOAD__
)


def _json_safe(value):
    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(
        value,
        list,
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        tuple,
    ):
        return {
            "__type__": "tuple",
            "items": [
                _json_safe(item)
                for item in value
            ],
        }

    if isinstance(
        value,
        dict,
    ):
        result = {}

        for key, item in value.items():
            result[str(key)] = _json_safe(
                item
            )

        return result

    if isinstance(
        value,
        set,
    ):
        return {
            "__type__": "set",
            "items": [
                _json_safe(item)
                for item in value
            ],
        }

    return {
        "__type__": type(
            value
        ).__name__,
        "repr": repr(
            value
        ),
    }


def _load_module():
    repository_root = os.path.abspath(
        PAYLOAD[
            "repository_root"
        ]
    )

    module_path = os.path.abspath(
        PAYLOAD[
            "target_module_path"
        ]
    )

    if repository_root not in sys.path:
        sys.path.insert(
            0,
            repository_root,
        )

    module_directory = os.path.dirname(
        module_path
    )

    if module_directory not in sys.path:
        sys.path.insert(
            0,
            module_directory,
        )

    module_name = os.path.splitext(
        os.path.basename(
            module_path
        )
    )[0]

    #
    # Python 3.
    #

    if sys.version_info[0] >= 3:

        import importlib.util

        spec = (
            importlib.util
            .spec_from_file_location(
                module_name,
                module_path,
            )
        )

        if spec is None:
            raise ImportError(
                "Unable to create module specification."
            )

        module = (
            importlib.util.module_from_spec(
                spec
            )
        )

        sys.modules[
            module_name
        ] = module

        spec.loader.exec_module(
            module
        )

        return module

    #
    # Python 2.
    #

    import imp

    module = imp.load_source(
        module_name,
        module_path,
    )

    sys.modules[
        module_name
    ] = module

    return module


def _resolve_class(
    module,
    class_name,
):
    current = module

    for part in class_name.split("."):
        current = getattr(
            current,
            part,
        )

    return current


def _invoke():
    module = _load_module()

    function_name = PAYLOAD[
        "target_function_name"
    ]

    function_inputs = PAYLOAD.get(
        "function_inputs",
        [],
    )

    callable_kind = PAYLOAD.get(
        "callable_kind",
        "function",
    )

    class_name = PAYLOAD.get(
        "target_class_name"
    )

    constructor_inputs = PAYLOAD.get(
        "constructor_inputs"
    )

    if callable_kind == "function":

        function = getattr(
            module,
            function_name,
        )

        return function(
            *function_inputs
        )

    if not class_name:

        raise ValueError(
            "Class callable requires target_class_name."
        )

    target_class = _resolve_class(
        module,
        class_name,
    )

    if callable_kind == "constructor":

        return target_class(
            *function_inputs
        )

    if callable_kind == "staticmethod":

        function = getattr(
            target_class,
            function_name,
        )

        return function(
            *function_inputs
        )

    if callable_kind == "classmethod":

        function = getattr(
            target_class,
            function_name,
        )

        return function(
            *function_inputs
        )

    if callable_kind == "instance_method":

        if constructor_inputs is None:

            raise ValueError(
                "Instance method requires constructor_inputs."
            )

        instance = target_class(
            *constructor_inputs
        )

        function = getattr(
            instance,
            function_name,
        )

        return function(
            *function_inputs
        )

    raise ValueError(
        "Unsupported callable kind: %s"
        % callable_kind
    )


def main():
    try:

        value = _invoke()

        result = {
            "status": "SUCCESS",
            "exception_type": None,
            "return_type": (
                type(
                    value
                ).__name__
                if value is not None
                else None
            ),
            "return_value": _json_safe(
                value
            ),
            "exception_message": None,
        }

        print(
            json.dumps(
                result
            )
        )

    except Exception as exc:

        result = {
            "status": "EXECUTION_FAILED",
            "exception_type": type(
                exc
            ).__name__,
            "return_type": None,
            "return_value": None,
            "exception_message": str(
                exc
            ),
        }

        print(
            json.dumps(
                result
            )
        )


if __name__ == "__main__":
    main()
'''

    #
    # IMPORTANT:
    #
    # json.dumps() gives us a JSON string.
    # repr() makes that string a valid Python string
    # literal inside both Python 2 and Python 3.
    #
    payload_literal = repr(
        payload_json
    )

    return runner_template.replace(
        "__PAYLOAD__",
        payload_literal,
    )


def _parse_runner_output(
    stdout,
    stderr,
):
    if not stdout:

        return FunctionExecutionResult(
            status="EXECUTION_FAILED",
            stdout=stdout,
            stderr=stderr,
            exception_type="RunnerError",
            exception_message=(
                "Runner produced no output."
            ),
        )

    lines = stdout.splitlines()

    result_line = None

    for line in reversed(
        lines
    ):

        line = line.strip()

        if not line:
            continue

        try:

            parsed = json.loads(
                line
            )

            if isinstance(
                parsed,
                dict,
            ):

                result_line = parsed
                break

        except Exception:
            continue

    if result_line is None:

        return FunctionExecutionResult(
            status="EXECUTION_FAILED",
            stdout=stdout,
            stderr=stderr,
            exception_type="RunnerError",
            exception_message=(
                "Runner output was not valid JSON."
            ),
        )

    return FunctionExecutionResult(
        status=result_line.get(
            "status",
            "EXECUTION_FAILED",
        ),
        return_value=result_line.get(
            "return_value"
        ),
        return_type=result_line.get(
            "return_type"
        ),
        stdout=stdout,
        stderr=stderr,
        exception_type=result_line.get(
            "exception_type"
        ),
        exception_message=result_line.get(
            "exception_message"
        ),
        timed_out=False,
    )


def execute_function(
    repository_path,
    module_path,
    function_name,
    inputs=None,
    python_executable=None,
    timeout=30,
    class_name=None,
    callable_kind="function",
    constructor_inputs=None,
):
    if inputs is None:
        inputs = []

    if python_executable is None:
        python_executable = "python"

    repository_path = os.path.abspath(
        repository_path
    )

    module_path = os.path.abspath(
        module_path
    )

    if not os.path.exists(
        repository_path
    ):

        return FunctionExecutionResult(
            status="EXECUTION_FAILED",
            exception_type="RepositoryNotFoundError",
            exception_message=(
                "Repository does not exist: %s"
                % repository_path
            ),
        )

    if not os.path.exists(
        module_path
    ):

        return FunctionExecutionResult(
            status="EXECUTION_FAILED",
            exception_type="ModuleNotFoundError",
            exception_message=(
                "Module does not exist: %s"
                % module_path
            ),
        )

    runner_script = _build_runner_script(
        repository_root=repository_path,
        target_module_path=module_path,
        target_function_name=function_name,
        function_inputs=inputs,
        target_class_name=class_name,
        callable_kind=callable_kind,
        constructor_inputs=constructor_inputs,
    )

    temporary_file = None

    python_command = (
        _normalize_python_command(
            python_executable
        )
    )

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as handle:

            handle.write(
                runner_script
            )

            temporary_file = handle.name

        command = (
            python_command
            + [
                temporary_file
            ]
        )

        completed = subprocess.run(
            command,
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return _parse_runner_output(
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    except subprocess.TimeoutExpired as exc:

        stdout = (
            exc.stdout
            if exc.stdout is not None
            else ""
        )

        stderr = (
            exc.stderr
            if exc.stderr is not None
            else ""
        )

        if isinstance(
            stdout,
            bytes,
        ):
            stdout = stdout.decode(
                errors="replace"
            )

        if isinstance(
            stderr,
            bytes,
        ):
            stderr = stderr.decode(
                errors="replace"
            )

        return FunctionExecutionResult(
            status="TIMEOUT",
            return_value=None,
            return_type=None,
            stdout=stdout,
            stderr=stderr,
            exception_type="TimeoutError",
            exception_message=(
                "Callable execution timed out."
            ),
            timed_out=True,
        )

    except FileNotFoundError:

        return FunctionExecutionResult(
            status="EXECUTION_FAILED",
            return_value=None,
            return_type=None,
            stdout="",
            stderr="",
            exception_type="PythonExecutableNotFoundError",
            exception_message=(
                "Unable to start Python executable: %s. "
                "Resolved command: %s"
                % (
                    python_executable,
                    python_command,
                )
            ),
            timed_out=False,
        )

    except Exception as exc:

        return FunctionExecutionResult(
            status="EXECUTION_FAILED",
            return_value=None,
            return_type=None,
            stdout="",
            stderr="",
            exception_type=type(
                exc
            ).__name__,
            exception_message=str(
                exc
            ),
            timed_out=False,
        )

    finally:

        if (
            temporary_file is not None
            and os.path.exists(
                temporary_file
            )
        ):

            try:
                os.remove(
                    temporary_file
                )
            except OSError:
                pass