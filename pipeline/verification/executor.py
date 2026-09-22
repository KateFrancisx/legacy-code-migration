import subprocess
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def to_dict(self):
        return {
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
        }


def execute_command(command, cwd, timeout=60):
    """
    Execute a command inside a repository.

    Args:
        command: List containing executable and arguments.
        cwd: Working directory / repository path.
        timeout: Maximum execution time in seconds.

    Returns:
        ExecutionResult
    """

    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return ExecutionResult(
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=False,
        )

    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="replace",
            )

        return ExecutionResult(
            return_code=-1,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )

    except OSError as exc:
        return ExecutionResult(
            return_code=-1,
            stdout="",
            stderr=str(exc),
            timed_out=False,
        )


def build_python_command(
    python_executable="python",
    module=None,
    module_args=None,
):
    """
    Build a Python command.

    python_executable can be:

        "python"
        "python3"
        "py"
        ["py", "-2"]
        ["py", "-3"]

    This allows the verification engine to execute the
    original and migrated repositories with different
    Python runtimes.
    """

    if isinstance(python_executable, str):
        command = [python_executable]
    else:
        command = list(python_executable)

    if module:
        command.extend(["-m", module])

    if module_args:
        command.extend(module_args)

    return command


def run_tests(
    repo_path,
    framework,
    python_executable="python",
    timeout=60,
):
    """
    Run the repository's tests using the detected framework.

    Supported frameworks:
        pytest
        unittest
        unknown
        none

    The Python runtime is explicitly supplied so that a
    Python 2 repository can be tested with Python 2 while
    a migrated repository is tested with Python 3.
    """

    if framework == "pytest":
        command = build_python_command(
            python_executable,
            module="pytest",
            module_args=["-q"],
        )

    elif framework == "unittest":
        command = build_python_command(
            python_executable,
            module="unittest",
            module_args=[
                "discover",
                "-v",
            ],
        )

    elif framework == "none":
        return ExecutionResult(
            return_code=0,
            stdout="No tests discovered.",
            stderr="",
            timed_out=False,
        )

    else:
        return ExecutionResult(
            return_code=2,
            stdout="",
            stderr=(
                "Unsupported or unknown test framework: "
                f"{framework}"
            ),
            timed_out=False,
        )

    return execute_command(
        command,
        cwd=repo_path,
        timeout=timeout,
    )