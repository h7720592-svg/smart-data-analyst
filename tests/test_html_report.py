"""Tests for HTML report builder module."""

import pytest

from src.export.html_report import build_html_report, save_report, _build_fallback_report


SAMPLE_SUMMARY = {
    "overview": {
        "rows": 100,
        "columns": 5,
        "cells": 500,
        "missing_cells": 10,
        "missing_pct": 2.0,
        "duplicate_rows": 5,
        "duplicate_pct": 5.0,
        "memory_mb": 1.5,
    },
    "columns": [
        {"name": "col_a", "dtype": "int64", "null_pct": 2.0, "unique_count": 50,
         "mean": 25.0, "std": 5.0, "min": 10.0, "max": 40.0},
        {"name": "col_b", "dtype": "object", "null_pct": 5.0, "unique_count": 10,
         "top_values": {"A": 30, "B": 20}},
    ],
}

SAMPLE_ISSUES = [
    {"type": "missing_values", "column": "col_a", "severity": "high",
     "description": "列 'col_a' 有 30% 的缺失值"},
    {"type": "outliers", "column": "col_b", "severity": "medium",
     "description": "列 'col_b' 有 10 个异常值"},
]


class TestFallbackReport:
    def test_generates_html(self):
        context = {
            "title": "Test Report",
            "generated_at": "2024-01-01 12:00:00",
            "metadata": {"filename": "test.csv"},
            "overview": SAMPLE_SUMMARY["overview"],
            "columns": SAMPLE_SUMMARY["columns"],
            "issues": [
                {"severity_class": "high", "description": "test issue"}
            ],
            "charts": [],
            "conversation": [
                {"role": "👤 用户", "content": "hello"},
            ],
            "profile_html": None,
            "chart_count": 0,
            "issue_count": 1,
            "message_count": 1,
        }
        html = _build_fallback_report(context)
        assert "<!DOCTYPE html>" in html
        assert "Test Report" in html
        assert "test issue" in html

    def test_includes_metrics(self):
        context = {
            "title": "Test",
            "generated_at": "2024-01-01",
            "metadata": {"filename": "test.csv"},
            "overview": SAMPLE_SUMMARY["overview"],
            "columns": [],
            "issues": [],
            "charts": [],
            "conversation": [],
            "profile_html": None,
            "chart_count": 0,
            "issue_count": 0,
            "message_count": 0,
        }
        html = _build_fallback_report(context)
        assert "100" in html  # rows
        assert "5" in html   # columns

    def test_no_issues_shows_success(self):
        context = {
            "title": "Test",
            "generated_at": "2024-01-01",
            "metadata": {"filename": "test.csv"},
            "overview": SAMPLE_SUMMARY["overview"],
            "columns": [],
            "issues": [],
            "charts": [],
            "conversation": [],
            "profile_html": None,
            "chart_count": 0,
            "issue_count": 0,
            "message_count": 0,
        }
        html = _build_fallback_report(context)
        assert "未检测到明显问题" in html


class TestBuildHTMLReport:
    def test_basic_report(self, tmp_path):
        """Test building a basic HTML report without figures."""
        html = build_html_report(
            df_summary=SAMPLE_SUMMARY,
            df_issues=SAMPLE_ISSUES,
            figures=[],
            messages=[{"role": "user", "content": "帮我分析数据"}],
            metadata={"filename": "test.csv", "file_type": "csv",
                      "rows": 100, "columns": 5},
        )
        assert isinstance(html, str)
        assert len(html) > 0
        assert "test.csv" in html

    def test_report_with_figures(self):
        """Test building a report that includes Plotly figures."""
        import plotly.express as px
        import pandas as pd

        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        fig = px.scatter(df, x="x", y="y")

        html = build_html_report(
            df_summary=SAMPLE_SUMMARY,
            df_issues=SAMPLE_ISSUES,
            figures=[{"explanation": "散点图", "figure": fig}],
            messages=[],
            metadata={"filename": "test.csv", "file_type": "csv"},
        )
        assert "散点图" in html

    def test_report_with_issues(self):
        html = build_html_report(
            df_summary=SAMPLE_SUMMARY,
            df_issues=SAMPLE_ISSUES,
            figures=[],
            messages=[],
            metadata={"filename": "test.csv", "file_type": "csv"},
        )
        # Should contain issue descriptions
        assert "30%" in html

    def test_report_empty(self):
        """Test building a report with minimal data."""
        html = build_html_report(
            df_summary={"overview": {}, "columns": []},
            df_issues=[],
            figures=[],
            messages=[],
            metadata={"filename": "empty.csv", "file_type": "csv"},
        )
        assert isinstance(html, str)
        assert len(html) > 0


class TestSaveReport:
    def test_saves_to_file(self, tmp_path):
        output = tmp_path / "report.html"
        result = save_report("<html>test</html>", str(output))
        assert result == str(output)
        assert output.exists()
        assert output.read_text() == "<html>test</html>"

    def test_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "subdir" / "nested" / "report.html"
        result = save_report("<html>test</html>", str(output))
        assert result == str(output)
        assert output.exists()
