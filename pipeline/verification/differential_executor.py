import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass
class FunctionExecutionResult:
    """
    Result produced by executing one function in an isolated
    Python process.
    """

    status: str
    return_value: object = None
    return_type: str = None
    stdout: str = ""
    stderr: str = ""
    exception_type: str = None
    exception_message: str = None
    timed_out: bool = False

    def to_dict(self):
        return {
            "status": self.status,
            "return_value": self.return_value,
            "return_type": self.return_type,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "timed_out": self.timed_out,
        }


# -------------------------------------------------------------------
# This script must itself be compatible with Python 2.7 and Python 3.
# -------------------------------------------------------------------

RUNNER_SCRIPT = r'''
import json
import os
import sys


# ---------------------------------------------------------
# Python 2 / Python 3 compatibility
# ---------------------------------------------------------

try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)


try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO


# ---------------------------------------------------------
# JSON-safe conversion
# ---------------------------------------------------------

def make_json_safe(value):

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, string_types):
        return value

    if isinstance(value, (list, tuple)):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            result[str(key)] = make_json_safe(item)

        return result

    if isinstance(value, set):
        return {
            "__type__": "set",
            "items": [
                make_json_safe(item)
                for item in value
            ],
        }

    try:
        return {
            "__type__": type(value).__name__,
            "repr": repr(value),
        }
    except Exception:
        return {
            "__type__": type(value).__name__,
            "repr": "<unrepresentable>",
        }


# ---------------------------------------------------------
# Module loading
# ---------------------------------------------------------

def load_module(module_file_path):

    if repository_root not in sys.path:
        sys.path.insert(
            0,
            repository_root,
        )

    module_name = os.path.splitext(
        os.path.basename(module_file_path)
    )[0]

    # Python 3
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            module_name,
            module_file_path,
        )

        if spec is None or spec.loader is None:
            raise ImportError(
                "Unable to create import specification."
            )

        module = importlib.util.module_from_spec(
            spec
        )

        spec.loader.exec_module(
            module
        )

        return module

    except ImportError:

        # Python 2
        import imp

        return imp.load_source(
            module_name,
            module_file_path,
        )


# ---------------------------------------------------------
# Function execution
# ---------------------------------------------------------

def execute_target_function():

    # Import/load the target module.
    try:

        module = load_module(
            target_module_path
        )

        function = getattr(
            module,
            target_function_name,
        )

        if not callable(function):
            raise TypeError(
                "Target attribute is not callable: "
                + target_function_name
            )

    except Exception as exc:

        return {
            "status": "IMPORT_FAILED",
            "return_value": None,
            "return_type": None,
            "stdout": "",
            "stderr": "",
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "timed_out": False,
        }

    # Capture stdout/stderr.
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    stdout_buffer = StringIO()
    stderr_buffer = StringIO()

    try:

        sys.stdout = stdout_buffer
        sys.stderr = stderr_buffer

        result_value = function(
            *function_inputs
        )

        return {
            "status": "SUCCESS",
            "return_value": make_json_safe(
                result_value
            ),
            "return_type": type(
                result_value
            ).__name__,
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "exception_type": None,
            "exception_message": None,
            "timed_out": False,
        }

    except Exception as exc:

        return {
            "status": "EXECUTION_FAILED",
            "return_value": None,
            "return_type": None,
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "timed_out": False,
        }

    finally:

        sys.stdout = original_stdout
        sys.stderr = original_stderr


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":

    result = execute_target_function()

    print(
        json.dumps(
            result,
            default=str,
        )
    )
'''


def _build_runner_script(
    repository_path,
    module_path,
    function_name,
    inputs,
):
    """
    Replace only dedicated placeholders.

    Using unique placeholders prevents accidental replacement
    of normal Python identifiers such as module_path.
    """

    replacements = {
        "__CODEMIGRATE_REPOSITORY_ROOT__": json.dumps(
            os.path.abspath(repository_path)
        ),

        "__CODEMIGRATE_TARGET_MODULE__": json.dumps(
            os.path.abspath(module_path)
        ),

        "__CODEMIGRATE_TARGET_FUNCTION__": json.dumps(
            function_name
        ),

        "__CODEMIGRATE_FUNCTION_INPUTS__": json.dumps(
            inputs,
            default=str,
        ),
    }

    script = RUNNER_SCRIPT

    # The runner source uses these exact assignment statements.
    script = script.replace(
        "repository_root",
        replacements[
            "__CODEMIGRATE_REPOSITORY_ROOT__"
        ],
    )

    script = script.replace(
        "target_module_path",
        replacements[
            "__CODEMIGRATE_TARGET_MODULE__"
        ],
    )

    script = script.replace(
        "target_function_name",
        replacements[
            "__CODEMIGRATE_TARGET_FUNCTION__"
        ],
    )

    script = script.replace(
        "function_inputs",
        replacements[
            "__CODEMIGRATE_FUNCTION_INPUTS__"
        ],
    )

    return script


def _parse_runner_output(stdout):
    """
    Convert the runner's JSON output into a dictionary.
    """

    stdout = stdout.strip()

    if not stdout:

        return {
            "status": "RUNNER_FAILED",
            "return_value": None,
            "return_type": None,
            "stdout": "",
            "stderr": "",
            "exception_type": "RunnerOutputError",
            "exception_message": (
                "The verification runner produced "
                "no JSON result."
            ),
            "timed_out": False,
        }

    try:

        return json.loads(
            stdout
        )

    except ValueError as exc:

        return {
            "status": "RUNNER_FAILED",
            "return_value": None,
            "return_type": None,
            "stdout": stdout,
            "stderr": "",
            "exception_type": "RunnerOutputError",
            "exception_message": (
                "Unable to parse verification runner "
                "output: "
                + str(exc)
            ),
            "timed_out": False,
        }


def execute_function(
    repository_path,
    module_path,
    function_name,
    inputs=None,
    python_executable=None,
    timeout=30,
):
    """
    Execute a function in an isolated Python subprocess.

    Supports different Python runtimes.

    Examples:

        python_executable="python"

        python_executable=["py", "-2"]

        python_executable=["py", "-3"]
    """

    if inputs is None:
        inputs = []

    if python_executable is None:
        python_executable = [
            sys.executable
        ]

    if isinstance(
        python_executable,
        str,
    ):
        python_command = [
            python_executable
        ]
    else:
        python_command = list(
            python_executable
        )

    if not python_command:
        raise ValueError(
            "python_executable cannot be empty."
        )

    repository_path = os.path.abspath(
        repository_path
    )

    module_path = os.path.abspath(
        module_path
    )

    if not os.path.isdir(
        repository_path
    ):
        raise IOError(
            "Repository not found: "
            + repository_path
        )

    if not os.path.isfile(
        module_path
    ):
        raise IOError(
            "Module not found: "
            + module_path
        )

    runner_script = _build_runner_script(
        repository_path=repository_path,
        module_path=module_path,
        function_name=function_name,
        inputs=inputs,
    )

    runner_path = None

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix="_verification_runner.py",
            delete=False,
            encoding="utf-8",
        ) as runner_file:

            runner_file.write(
                runner_script
            )

            runner_path = runner_file.name

        command = (
            python_command
            + [
                runner_path
            ]
        )

        process = subprocess.run(
            command,
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        parsed = _parse_runner_output(
            process.stdout
        )

        if process.stderr:

            existing_stderr = parsed.get(
                "stderr",
                "",
            )

            if existing_stderr:

                parsed["stderr"] = (
                    existing_stderr
                    + "\n"
                    + process.stderr
                )

            else:

                parsed["stderr"] = (
                    process.stderr
                )

        return FunctionExecutionResult(
            status=parsed.get(
                "status",
                "RUNNER_FAILED",
            ),
            return_value=parsed.get(
                "return_value"
            ),
            return_type=parsed.get(
                "return_type"
            ),
            stdout=parsed.get(
                "stdout",
                "",
            ),
            stderr=parsed.get(
                "stderr",
                "",
            ),
            exception_type=parsed.get(
                "exception_type"
            ),
            exception_message=parsed.get(
                "exception_message"
            ),
            timed_out=parsed.get(
                "timed_out",
                False,
            ),
        )

    except subprocess.TimeoutExpired as exc:

        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(
            stdout,
            bytes,
        ):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(
            stderr,
            bytes,
        ):
            stderr = stderr.decode(
                "utf-8",
                errors="replace",
            )

        return FunctionExecutionResult(
            status="TIMEOUT",
            stdout=stdout,
            stderr=stderr,
            exception_type="Timeout",
            exception_message=(
                "Function execution exceeded "
                + str(timeout)
                + " seconds."
            ),
            timed_out=True,
        )

    finally:

        if runner_path:

            try:
                os.remove(
                    runner_path
                )

            except OSError:
                pass