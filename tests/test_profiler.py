"""Tests for profiler module."""

import numpy as np
import pandas as pd
import pytest

from src.profiler import (
    compute_summary,
    detect_issues,
    get_correlation_matrix,
    fill_missing_values,
    clip_outliers,
    drop_constant_columns,
    clean_dataframe,
)


@pytest.fixture
def clean_df():
    """Create a clean DataFrame with no issues."""
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", "Diana"],
        "age": [25, 30, 35, 28],
        "score": [85.5, 92.0, 78.3, 88.0],
        "city": ["NYC", "LA", "SF", "NYC"],
    })


@pytest.fixture
def messy_df():
    """Create a DataFrame with various data quality issues."""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "name": ["A", "B", None, "D", "E", None, "G", None, None, None],
        "age": [25, 30, 35, 28, 22, 30, 1000, 28, 30, 30],  # 1000 is outlier
        "score": [85, 92, 78, 88, 85, 92, 78, 88, 85, 92],
        "constant_col": ["x", "x", "x", "x", "x", "x", "x", "x", "x", "x"],
    })


class TestComputeSummary:
    """Summary computation tests."""

    def test_basic_summary(self, clean_df):
        summary = compute_summary(clean_df)
        overview = summary["overview"]
        assert overview["rows"] == 4
        assert overview["columns"] == 4
        assert overview["missing_cells"] == 0
        assert overview["duplicate_rows"] == 0

    def test_column_info(self, clean_df):
        summary = compute_summary(clean_df)
        columns = summary["columns"]
        assert len(columns) == 4
        # Check numeric column
        age_col = next(c for c in columns if c["name"] == "age")
        assert age_col["mean"] is not None
        assert age_col["dtype"] in ("int64", "Int64")

    def test_with_missing_values(self, messy_df):
        summary = compute_summary(messy_df)
        overview = summary["overview"]
        assert overview["missing_cells"] > 0

    def test_with_constant_column(self, messy_df):
        summary = compute_summary(messy_df)
        const_col = next(
            c for c in summary["columns"] if c["name"] == "constant_col"
        )
        assert const_col["unique_count"] == 1


class TestDetectIssues:
    """Issue detection tests."""

    def test_clean_data_no_issues(self, clean_df):
        issues = detect_issues(clean_df)
        # Clean data should have few or no issues
        high_severity = [i for i in issues if i["severity"] == "high"]
        assert len(high_severity) == 0

    def test_detect_missing_values(self):
        df = pd.DataFrame({
            "a": [1, 2, None, None, None],
            "b": [10, 20, 30, 40, 50],
        })
        issues = detect_issues(df)
        missing_issues = [i for i in issues if i["type"] == "missing_values"]
        assert len(missing_issues) > 0
        assert missing_issues[0]["column"] == "a"

    def test_detect_outliers(self):
        df = pd.DataFrame({
            "value": [1, 2, 3, 4, 5, 100],  # 100 is outlier
        })
        issues = detect_issues(df)
        outlier_issues = [i for i in issues if i["type"] == "outliers"]
        assert len(outlier_issues) > 0

    def test_detect_constant_column(self, messy_df):
        issues = detect_issues(messy_df)
        const_issues = [i for i in issues if i["type"] == "constant_column"]
        assert len(const_issues) > 0
        assert const_issues[0]["column"] == "constant_col"

    def test_detect_duplicates(self):
        df = pd.DataFrame({
            "a": [1, 1, 2, 2, 2],
            "b": [10, 10, 20, 20, 20],
        })
        issues = detect_issues(df)
        dup_issues = [i for i in issues if i["type"] == "duplicates"]
        assert len(dup_issues) > 0

    def test_detect_skewness(self):
        # Create heavily skewed data
        np.random.seed(42)
        df = pd.DataFrame({
            "skewed": np.random.exponential(scale=2, size=100),
        })
        issues = detect_issues(df)
        skew_issues = [i for i in issues if i["type"] == "skewness"]
        assert len(skew_issues) > 0


class TestCorrelation:
    """Correlation matrix tests."""

    def test_correlation_with_numeric(self, clean_df):
        corr = get_correlation_matrix(clean_df)
        assert corr is not None
        assert "age" in corr["columns"]
        assert "score" in corr["columns"]

    def test_correlation_no_numeric(self):
        df = pd.DataFrame({
            "a": ["x", "y", "z"],
            "b": ["1", "2", "3"],
        })
        corr = get_correlation_matrix(df)
        assert corr is None

    def test_correlation_single_numeric(self):
        df = pd.DataFrame({
            "a": ["x", "y", "z"],
            "num": [1, 2, 3],
        })
        corr = get_correlation_matrix(df)
        assert corr is None  # Need at least 2 numeric cols


# ── Data Cleaning Tests ─────────────────────────────────────────────────


class TestFillMissingValues:
    def test_fill_numeric_with_median(self):
        df = pd.DataFrame({
            "a": [1.0, 2.0, None, 4.0, 5.0],
            "b": ["x", None, "y", "z", None],
        })
        result = fill_missing_values(df, strategy="auto")
        assert result["a"].isna().sum() == 0
        assert result["b"].isna().sum() == 0
        # Median of [1,2,4,5] is 3.0
        assert result.loc[2, "a"] == 3.0

    def test_fill_with_mean_strategy(self):
        df = pd.DataFrame({"a": [10.0, 20.0, None]})
        result = fill_missing_values(df, strategy="mean")
        assert result["a"].isna().sum() == 0
        assert result.loc[2, "a"] == 15.0

    def test_fill_drop_strategy(self):
        df = pd.DataFrame({
            "a": [1, 2, None],
            "b": [4, 5, 6],
        })
        result = fill_missing_values(df, strategy="drop")
        assert len(result) == 2
        assert result["a"].isna().sum() == 0

    def test_no_missing_values(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = fill_missing_values(df, strategy="auto")
        pd.testing.assert_frame_equal(result, df)


class TestClipOutliers:
    def test_clip_iqr(self):
        df = pd.DataFrame({"value": [1, 2, 3, 4, 5, 100]})
        result = clip_outliers(df, method="iqr")
        # The extreme value 100 should be clipped
        assert result["value"].max() < 100

    def test_clip_percentile(self):
        df = pd.DataFrame({"value": list(range(100))})
        result = clip_outliers(df, method="percentile")
        # Should clip extreme values
        assert result["value"].min() >= 0  # approximately 1st percentile
        assert result["value"].max() <= 99  # approximately 99th percentile

    def test_clip_specific_columns(self):
        df = pd.DataFrame({
            "a": [1, 2, 3, 4, 100],
            "b": [10, 20, 30, 40, 500],
        })
        result = clip_outliers(df, method="iqr", columns=["a"])
        # Only column 'a' should be clipped
        assert result["a"].max() < 100
        # Column 'b' should be unchanged
        assert result["b"].max() == 500

    def test_non_numeric_columns_ignored(self):
        df = pd.DataFrame({
            "num": [1, 2, 3, 4, 100],
            "cat": ["a", "b", "c", "d", "e"],
        })
        result = clip_outliers(df, method="iqr")
        assert list(result["cat"]) == ["a", "b", "c", "d", "e"]


class TestDropConstantColumns:
    def test_drop_constant_col(self):
        df = pd.DataFrame({
            "a": [1, 2, 3],
            "constant": ["x", "x", "x"],
        })
        result = drop_constant_columns(df)
        assert "constant" not in result.columns
        assert "a" in result.columns

    def test_no_constant_cols(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = drop_constant_columns(df)
        assert list(result.columns) == ["a", "b"]


class TestCleanDataFrame:
    def test_full_clean(self):
        df = pd.DataFrame({
            "name": ["Alice", "Bob", None, "Diana"],
            "age": [25, 30, None, 28],
            "score": [85.0, 92.0, 78.0, 999.0],  # 999 is outlier
            "constant": ["x", "x", "x", "x"],
        })
        result, report = clean_dataframe(
            df, fill_strategy="auto", outlier_method="iqr", drop_constant=True
        )
        assert report["original_missing"] > 0
        assert report["remaining_missing"] == 0
        assert "constant" not in result.columns
        assert result["score"].max() < 999

    def test_clean_report_values(self):
        df = pd.DataFrame({
            "a": [1, 2, None, 4],
            "b": [5, 6, 7, 8],
        })
        result, report = clean_dataframe(df)
        assert report["original_rows"] == 4
        assert report["original_missing"] == 1
        assert report["remaining_missing"] == 0
