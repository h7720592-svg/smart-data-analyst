"""Safe code execution sandbox for LLM-generated Python code.

Implements a three-layer defense:
1. AST import whitelist — only allow safe modules
2. Restricted builtins — block dangerous functions
3. Process timeout — prevent infinite loops
"""

import ast
import logging
import multiprocessing
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Security Configuration ──────────────────────────────────────────────

# Allowed import modules
ALLOWED_IMPORTS = {
    "pandas",
    "numpy",
    "plotly",
    "plotly.express",
    "plotly.graph_objects",
    "plotly.graph_objs",
    "matplotlib",
    "matplotlib.pyplot",
    "seaborn",
    "scipy",
    "scipy.stats",
    "scipy.signal",
    "json",
    "math",
    "statistics",
    "datetime",
    "collections",
    "itertools",
    "re",
    "functools",
    "typing",
    "warnings",
    "copy",
    "operator",
    # NLP / text processing
    "jieba",
    "collections",
    "re",
    "string",
}

# Builtins to block at the execution level
# __import__ is allowed here (needed for Python's import statement to work)
# but blocked at the AST level for explicit calls.
BUILTINS_TO_BLOCK = {
    "open",
    "exec",
    "eval",
    "compile",
    "input",
    "breakpoint",
    "memoryview",
    "__builtins__",
}

# Builtins blocked at AST level (explicit calls)
# These are allowed in builtins for implicit use but blocked for explicit calls
AST_BLOCKED_CALLS = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "input",
    "breakpoint",
    "memoryview",
    "getattr",
    "setattr",
    "delattr",
}

# Maximum execution time (seconds)
MAX_EXECUTION_TIME = 30

# Memory limit in bytes (2GB per process)
MAX_MEMORY_BYTES = 2 * 1024 * 1024 * 1024


@dataclass
class ExecutionResult:
    """Result of code execution."""

    success: bool
    figures: list = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    error_type: str = ""


# ── AST Validation ───────────────────────────────────────────────────────


class CodeValidator(ast.NodeVisitor):
    """AST visitor that validates code safety.

    Checks:
    - All imports are in the whitelist
    - No dangerous function calls
    - No attribute access patterns used for sandbox escape
    """

    def __init__(self):
        self.errors: list[str] = []
        self.has_code = False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name
            # Check if the import or its top-level module is allowed
            if not self._is_import_allowed(name):
                self.errors.append(f"禁止导入模块: {name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module is None:
            self.generic_visit(node)
            return
        if not self._is_import_allowed(node.module):
            self.errors.append(f"禁止导入模块: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check for direct calls to blocked builtins (AST-level blocking)
        if isinstance(node.func, ast.Name) and node.func.id in AST_BLOCKED_CALLS:
            self.errors.append(f"禁止调用函数: {node.func.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Check for accessing dangerous attributes like __class__, __bases__, etc.
        if node.attr.startswith("__") and node.attr.endswith("__"):
            # Allow common safe dunder attributes
            safe_dunders = {"__name__", "__doc__", "__dict__", "__module__"}
            if node.attr not in safe_dunders:
                self.errors.append(f"禁止访问特殊属性: {node.attr}")
        self.generic_visit(node)

    def _is_import_allowed(self, module_name: str) -> bool:
        """Check if a module import is allowed."""
        if module_name in ALLOWED_IMPORTS:
            return True
        # Check top-level module
        top_level = module_name.split(".")[0]
        if top_level in ALLOWED_IMPORTS:
            return True
        return False


def validate_code_ast(code: str) -> tuple[bool, list[str]]:
    """Validate code safety using AST analysis.

    Args:
        code: Python source code string.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"语法错误: {e}"]

    validator = CodeValidator()
    validator.visit(tree)

    if validator.errors:
        return False, validator.errors

    return True, []


# ── Restricted Execution Environment ─────────────────────────────────────


def _build_restricted_globals(df: pd.DataFrame) -> dict:
    """Build a restricted globals dict for code execution.

    Args:
        df: The DataFrame to make available as 'df'.

    Returns:
        dict of safe globals.
    """
    # Build safe __builtins__
    import builtins as _builtins_module

    safe_builtins = {}
    for name in dir(_builtins_module):
        if name.startswith("_") and name.endswith("_"):
            # Allow safe dunder names (including __import__ needed for import statements)
            if name in (
                "__name__", "__doc__", "__package__", "__loader__",
                "__spec__", "__build_class__", "__import__",
            ):
                safe_builtins[name] = getattr(_builtins_module, name)
            continue
        if name in BUILTINS_TO_BLOCK:
            continue
        safe_builtins[name] = getattr(_builtins_module, name)

    # Add print function that captures output
    safe_globals: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
        "df": df,
        "pd": pd,
    }

    return safe_globals


def _execute_in_process(
    code: str,
    df: pd.DataFrame,
    result_queue: multiprocessing.Queue,
) -> None:
    """Execute code in a subprocess (target function).

    Args:
        code: Python source code.
        df: DataFrame to make available.
        result_queue: Queue to send results back to parent.
    """
    import io
    import warnings

    # Suppress warnings
    warnings.filterwarnings("ignore")

    # Capture stdout
    stdout_capture = io.StringIO()
    sys.stdout = stdout_capture
    sys.stderr = stdout_capture

    try:
        # Validate code
        is_valid, errors = validate_code_ast(code)
        if not is_valid:
            result_queue.put({
                "success": False,
                "error": "; ".join(errors),
                "error_type": "ValidationError",
                "stdout": "",
            })
            return

        # Compile code (restricted)
        try:
            compiled = compile(code, "<llm_generated>", "exec")
        except SyntaxError as e:
            result_queue.put({
                "success": False,
                "error": f"语法错误: {e}",
                "error_type": "SyntaxError",
                "stdout": stdout_capture.getvalue(),
            })
            return

        # Build restricted globals
        restricted_globals = _build_restricted_globals(df)
        restricted_locals: dict[str, Any] = {}

        # Execute
        exec(compiled, restricted_globals, restricted_locals)

        # Extract figures
        figures = []
        if "fig" in restricted_locals:
            figures.append(restricted_locals["fig"])
        elif "fig" in restricted_globals:
            figure_val = restricted_globals["fig"]
            # Don't capture the module itself
            from plotly.graph_objects import Figure as GoFigure
            from plotly.basedatatypes import BaseFigure

            if isinstance(figure_val, (GoFigure, BaseFigure)):
                figures.append(figure_val)

        result_queue.put({
            "success": True,
            "figures": figures,
            "stdout": stdout_capture.getvalue(),
            "error": None,
            "error_type": "",
        })

    except Exception as e:
        result_queue.put({
            "success": False,
            "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            "error_type": type(e).__name__,
            "stdout": stdout_capture.getvalue(),
        })

    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


# ── Public API ────────────────────────────────────────────────────────────


def execute(
    code: str,
    df: pd.DataFrame,
    timeout: int = MAX_EXECUTION_TIME,
) -> ExecutionResult:
    """Safely execute LLM-generated Python code.

    Args:
        code: Python source code to execute.
        df: DataFrame available as 'df' in the code.
        timeout: Maximum execution time in seconds.

    Returns:
        ExecutionResult with figures (Plotly Figure objects) and/or error info.
    """
    # Pre-validation (fast, in-process)
    is_valid, errors = validate_code_ast(code)
    if not is_valid:
        return ExecutionResult(
            success=False,
            error="; ".join(errors),
            error_type="ValidationError",
            stdout="",
        )

    # Execute in subprocess with timeout
    ctx = multiprocessing.get_context("spawn")
    result_queue: multiprocessing.Queue = ctx.Queue()

    process = ctx.Process(
        target=_execute_in_process,
        args=(code, df, result_queue),
        daemon=True,
    )
    process.start()
    process.join(timeout=timeout)

    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
        return ExecutionResult(
            success=False,
            error=f"代码执行超时（>{timeout}秒），可能存在死循环。",
            error_type="TimeoutError",
        )

    if result_queue.empty():
        return ExecutionResult(
            success=False,
            error="代码执行异常终止，无返回结果。",
            error_type="ProcessError",
        )

    result = result_queue.get()

    if result["success"]:
        return ExecutionResult(
            success=True,
            figures=result.get("figures", []),
            stdout=result.get("stdout", ""),
        )
    else:
        return ExecutionResult(
            success=False,
            error=result.get("error", "未知错误"),
            error_type=result.get("error_type", "UnknownError"),
            stdout=result.get("stdout", ""),
        )


def execute_with_retry(
    code: str,
    df: pd.DataFrame,
    retry_callback,
    max_retries: int = 2,
) -> ExecutionResult:
    """Execute code with automatic retry on failure.

    Args:
        code: Python source code.
        df: DataFrame available as 'df'.
        retry_callback: Callable(code, error_message) -> new_code.
            Called on each failure to get fixed code from LLM.
        max_retries: Maximum number of retry attempts.

    Returns:
        ExecutionResult. If retries exhausted, returns the last failure.
    """
    current_code = code
    last_error = ""

    for attempt in range(max_retries + 1):
        result = execute(current_code, df)

        if result.success:
            return result

        last_error = result.error or "Unknown error"
        logger.warning(
            "Code execution failed (attempt %d/%d): %s",
            attempt + 1,
            max_retries + 1,
            result.error_type,
        )

        if attempt < max_retries:
            try:
                current_code = retry_callback(current_code, last_error)
            except Exception as e:
                logger.error("Retry callback failed: %s", e)
                return result

    return ExecutionResult(
        success=False,
        error=f"重试 {max_retries} 次后仍然失败。最后错误: {last_error}",
        error_type="MaxRetriesExceeded",
    )
