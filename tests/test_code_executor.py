"""Tests for code_executor sandbox."""

import pandas as pd
import pytest

from src.llm.code_executor import (
    AST_BLOCKED_CALLS,
    CodeValidator,
    execute,
    validate_code_ast,
)


@pytest.fixture
def sample_df():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie"],
        "age": [25, 30, 35],
        "score": [85.5, 92.0, 78.3],
        "city": ["NYC", "LA", "SF"],
    })


class TestASTValidation:
    """AST validation tests."""

    def test_valid_imports(self):
        is_valid, errors = validate_code_ast(
            "import pandas as pd\nimport plotly.express as px"
        )
        assert is_valid

    def test_blocked_import_os(self):
        is_valid, errors = validate_code_ast("import os")
        assert not is_valid
        assert any("os" in e for e in errors)

    def test_blocked_import_subprocess(self):
        is_valid, errors = validate_code_ast("import subprocess")
        assert not is_valid

    def test_blocked_import_requests(self):
        is_valid, errors = validate_code_ast("from requests import get")
        assert not is_valid

    def test_blocked_import_socket(self):
        is_valid, errors = validate_code_ast("import socket")
        assert not is_valid

    def test_blocked_open_call(self):
        is_valid, errors = validate_code_ast("open('/etc/passwd')")
        assert not is_valid
        assert any("open" in e for e in errors)

    def test_blocked_exec_call(self):
        is_valid, errors = validate_code_ast("exec('print(1)')")
        assert not is_valid

    def test_blocked_eval_call(self):
        is_valid, errors = validate_code_ast("eval('1+1')")
        assert not is_valid

    def test_blocked_compile_call(self):
        is_valid, errors = validate_code_ast("compile('x=1', '', 'exec')")
        assert not is_valid

    def test_blocked_dunder_import(self):
        """Test that __import__ is blocked."""
        is_valid, errors = validate_code_ast("__import__('os')")
        assert not is_valid

    def test_valid_pandas_code(self):
        is_valid, errors = validate_code_ast(
            "import pandas as pd\nresult = df.groupby('city').mean()"
        )
        assert is_valid

    def test_valid_plotly_code(self):
        is_valid, errors = validate_code_ast(
            "import plotly.express as px\n"
            "fig = px.bar(df, x='city', y='age', title='Test')"
        )
        assert is_valid

    def test_syntax_error(self):
        is_valid, errors = validate_code_ast("this is not valid python!!!")
        assert not is_valid


class TestExecute:
    """Code execution tests."""

    def test_execute_valid_code(self, sample_df):
        code = "import plotly.express as px\nfig = px.bar(df, x='city', y='age')"
        result = execute(code, sample_df)
        assert result.success
        assert len(result.figures) == 1

    def test_execute_pandas_operation(self, sample_df):
        """Test that pandas operations that don't produce figures work."""
        code = (
            "import pandas as pd\n"
            "result = df['age'].mean()\n"
            "# No fig variable assigned - this is fine for computation\n"
        )
        result = execute(code, sample_df)
        # Should not crash; no figure expected
        assert result.error is None or "ValidationError" not in str(result.error)

    def test_execute_with_missing_values(self):
        df = pd.DataFrame({
            "x": [1, 2, None, 4],
            "y": [10, None, 30, 40],
        })
        code = (
            "import plotly.express as px\n"
            "clean = df.dropna()\n"
            "fig = px.scatter(clean, x='x', y='y')"
        )
        result = execute(code, df)
        assert result.success

    def test_execute_timeout(self, sample_df):
        """Test that infinite loops are killed."""
        code = "while True: pass"
        result = execute(code, sample_df, timeout=1)
        assert not result.success
        # Should be a timeout or process error
        assert result.error_type in ("TimeoutError", "ProcessError", "ValidationError")

    def test_execute_blocked_code(self, sample_df):
        """Test that code with blocked operations fails validation."""
        code = "import os\nos.system('ls')"
        result = execute(code, sample_df)
        assert not result.success

    def test_execute_syntax_error(self, sample_df):
        code = "fig = px.bar(df, x='city'  # missing closing paren"
        result = execute(code, sample_df)
        assert not result.success

    def test_execute_returns_correct_figure(self, sample_df):
        code = "import plotly.express as px\nfig = px.histogram(df, x='age')"
        result = execute(code, sample_df)
        assert result.success
        assert len(result.figures) == 1
        from plotly.graph_objects import Figure

        assert isinstance(result.figures[0], Figure)


class TestCodeValidator:
    """CodeValidator class tests."""

    def test_no_code(self):
        import ast

        code = ""
        validator = CodeValidator()
        try:
            validator.visit(ast.parse(code))
        except SyntaxError:
            pass
        assert len(validator.errors) == 0

    def test_blocked_attribute_access(self):
        import ast

        code = "x.__class__.__bases__"
        validator = CodeValidator()
        validator.visit(ast.parse(code))
        # Should flag __class__ and __bases__ access
        assert len(validator.errors) > 0
