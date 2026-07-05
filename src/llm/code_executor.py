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
# NOTE: matplotlib/seaborn are deliberately excluded — they can hang on headless
# Windows subprocesses. All visualization is handled by plotly.
ALLOWED_IMPORTS = {
    "pandas",
    "numpy",
    "plotly",
    "plotly.express",
    "plotly.graph_objects",
    "plotly.graph_objs",
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
    "random",
    "textwrap",
    "hashlib",
    # NLP / text processing
    "jieba",
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

# Method/attribute calls blocked at AST level — these would hang the process
AST_BLOCKED_ATTR_CALLS = {
    "show",       # matplotlib plt.show() — tries to open GUI, hangs on headless
    "show_block", # matplotlib figure.show() — same issue
}

# Maximum execution time (seconds)
MAX_EXECUTION_TIME = 60


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


# Built-in names always available in Python
_PYTHON_BUILTINS = set(__builtins__.keys()) if hasattr(__builtins__, 'keys') else set(dir(__builtins__))


class UndefinedVariableChecker(ast.NodeVisitor):
    """AST visitor that checks for potentially undefined variable references.

    Catches patterns like:
        [w for w in positive_words if w]   # positive_words never defined
        df['col'].apply(lambda x: x in word_list)  # word_list never defined
    """

    def __init__(self):
        self.defined_names: set[str] = {
            # Always available in execution context
            "df", "pd", "fig",
            # Common imports (we also track imports dynamically)
        }
        self.imported_names: set[str] = set()
        self.issues: list[str] = []
        # Track scopes for comprehensions and lambdas
        self.scope_stack: list[set[str]] = []

    def _is_known(self, name: str) -> bool:
        if name in _PYTHON_BUILTINS:
            return True
        if name in self.defined_names:
            return True
        if name in self.imported_names:
            return True
        for scope in self.scope_stack:
            if name in scope:
                return True
        return False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.imported_names.add(name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            if name == "*":
                continue
            self.imported_names.add(name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Visit RHS first in case RHS references names defined earlier
        # Use self.visit (not generic_visit) so compound nodes (ListComp, Lambda, etc.)
        # dispatch to their specific visitor methods
        for target in node.targets:
            self.visit(node.value)  # visit value first
            self._add_target(target)
        # Don't generic_visit again — we already visited node.value

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self._add_target(node.target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value:
            self.visit(node.value)
        if node.target:
            self._add_target(node.target)

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)  # use visit() so Name nodes dispatch to visit_Name
        self._add_target(node.target)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Track function name as defined
        self.defined_names.add(node.name)
        # Push a scope for arguments
        arg_names = {a.arg for a in node.args.args}
        self.scope_stack.append(arg_names)
        for stmt in node.body:
            self.visit(stmt)
        self.scope_stack.pop()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Push scope for lambda arguments
        arg_names = {a.arg for a in node.args.args}
        self.scope_stack.append(arg_names)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        comp_names: set[str] = set()
        # First pass: collect all iteration variable names
        for gen in node.generators:
            self._add_target(gen.target, comp_names)
        # Push scope BEFORE visiting sub-expressions
        self.scope_stack.append(comp_names)
        for gen in node.generators:
            self.visit(gen.iter)
            for if_clause in gen.ifs:
                self.visit(if_clause)
        self.visit(node.key)
        self.visit(node.value)
        self.scope_stack.pop()

    def _visit_comprehension(self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp) -> None:
        comp_names: set[str] = set()
        # First pass: collect all iteration variable names
        for gen in node.generators:
            self._add_target(gen.target, comp_names)
        # Push scope BEFORE visiting any sub-expressions
        self.scope_stack.append(comp_names)
        # Now visit iter sources (checked against outer scope) and element (against comp scope)
        for gen in node.generators:
            self.visit(gen.iter)  # use visit() to dispatch to visit_Name
            for if_clause in gen.ifs:
                self.visit(if_clause)  # use visit() to dispatch to visit_Name
        self.visit(node.elt)  # use visit() to dispatch to visit_Name
        self.scope_stack.pop()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            if not self._is_known(node.id):
                self.issues.append(
                    f"变量 '{node.id}' 在第 {node.lineno} 行被引用，但未找到其定义。"
                    f"请确保在引用前已赋值或导入该名称。"
                )
        elif isinstance(node.ctx, ast.Store):
            self.defined_names.add(node.id)

    def _add_target(self, target: ast.AST, target_set: set[str] | None = None) -> None:
        """Extract names from an assignment target."""
        s = target_set if target_set is not None else self.defined_names
        if isinstance(target, ast.Name):
            s.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._add_target(elt, s)
        elif isinstance(target, ast.Starred):
            self._add_target(target.value, s)
        elif isinstance(target, ast.Subscript):
            # e.g. df['col'] — track 'df' is already known, subscription is fine
            pass


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

        # Check for blocked method calls (e.g., plt.show() hangs on headless systems)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in AST_BLOCKED_ATTR_CALLS:
                self.errors.append(
                    f"禁止调用方法: .{node.func.attr}() — 会导致进程挂起"
                )

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


def validate_variable_definitions(code: str) -> list[str]:
    """Check for potentially undefined variable references using AST.

    Args:
        code: Python source code string.

    Returns:
        List of warning/error messages about undefined variables.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # Syntax errors are handled by validate_code_ast

    checker = UndefinedVariableChecker()
    checker.visit(tree)
    return checker.issues


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
    import os
    import threading
    import warnings

    # ── Critical: prevent matplotlib from hanging on Windows without a display ──
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Suppress warnings
    warnings.filterwarnings("ignore")

    # Capture stdout
    stdout_capture = io.StringIO()
    sys.stdout = stdout_capture
    sys.stderr = stdout_capture

    # ── Internal timeout: kill the process from within if code hangs ──
    # This is a second layer of defense (parent process also has a timeout).
    # We use a slightly shorter timeout so we can capture diagnostics before
    # the parent kills us.
    _INTERNAL_TIMEOUT = 55  # seconds (parent timeout is 60s)

    def _on_timeout():
        """Called from timer thread when execution hangs."""
        # Write diagnostic info to a temporary file that the parent can read
        try:
            import tempfile
            diagnostic = {
                "error": "代码在子进程内部超时",
                "stdout": stdout_capture.getvalue(),
            }
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, prefix="sandbox_diag_"
            ) as f:
                import json as _json
                _json.dump(diagnostic, f, ensure_ascii=False)
        except Exception:
            pass
        os._exit(1)

    _timer = threading.Timer(_INTERNAL_TIMEOUT, _on_timeout)
    _timer.daemon = True
    _timer.start()

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

        # Check for undefined variable references
        var_issues = validate_variable_definitions(code)
        if var_issues:
            result_queue.put({
                "success": False,
                "error": "代码中存在未定义变量:\n" + "\n".join(f"  • {i}" for i in var_issues),
                "error_type": "UndefinedVariableError",
                "stdout": stdout_capture.getvalue(),
            })
            return

        # ── Save generated code for debugging ──
        try:
            import tempfile as _tmp
            _log_path = _tmp.gettempdir() + "/sandbox_last_code.py"
            with open(_log_path, "w", encoding="utf-8") as _f:
                _f.write(code)
        except Exception:
            pass

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

        # Build restricted globals (also used as locals so imports are
        # visible inside functions defined in the executed code)
        restricted_globals = _build_restricted_globals(df)

        # Execute — using the same dict for globals and locals ensures that
        # 'import jieba' adds jieba to globals where functions can find it
        exec(compiled, restricted_globals)

        # Extract figures (restricted_globals now serves as both globals and locals)
        figures = []
        if "fig" in restricted_globals:
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
        _timer.cancel()
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

    # Check for undefined variable references (fast, in-process)
    var_issues = validate_variable_definitions(code)
    if var_issues:
        return ExecutionResult(
            success=False,
            error="代码中存在未定义变量:\n" + "\n".join(f"  • {i}" for i in var_issues),
            error_type="UndefinedVariableError",
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
