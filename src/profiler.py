"""Data profiler module: auto-EDA, statistics, and data quality checks."""

from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# Sampling threshold: datasets larger than this will be sampled for profiling
MAX_PROFILE_ROWS = 200_000


def compute_summary(df: pd.DataFrame) -> dict:
    """Compute comprehensive summary statistics for a DataFrame.

    Args:
        df: Input DataFrame.

    Returns:
        dict with overview and per-column statistics.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    total_cells = total_rows * total_cols

    # Overall stats
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    # Column-level stats
    columns_info = []
    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        unique_count = int(series.nunique())
        info = {
            "name": col,
            "dtype": str(series.dtype),
            "null_count": null_count,
            "null_pct": round(null_count / total_rows * 100, 1) if total_rows > 0 else 0,
            "unique_count": unique_count,
            "unique_pct": round(unique_count / total_rows * 100, 1) if total_rows > 0 else 0,
        }

        # Numeric column stats
        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) > 0:
                info.update({
                    "mean": round(float(clean.mean()), 2),
                    "median": round(float(clean.median()), 2),
                    "std": round(float(clean.std()), 2),
                    "min": round(float(clean.min()), 2),
                    "max": round(float(clean.max()), 2),
                    "q25": round(float(clean.quantile(0.25)), 2),
                    "q75": round(float(clean.quantile(0.75)), 2),
                    "skewness": round(float(clean.skew()), 2),
                    "zeros_count": int((clean == 0).sum()),
                    "zeros_pct": round((clean == 0).sum() / len(clean) * 100, 1),
                    "negative_count": int((clean < 0).sum()),
                })
            else:
                info.update({"mean": None, "median": None, "std": None})

        # Categorical column stats
        elif pd.api.types.is_object_dtype(series) or isinstance(series.dtype, pd.CategoricalDtype):
            clean = series.dropna()
            if len(clean) > 0:
                top_values = clean.value_counts().head(5).to_dict()
                info["top_values"] = {str(k): int(v) for k, v in top_values.items()}
                info["empty_string_count"] = int((clean == "").sum())
            else:
                info["top_values"] = {}

        columns_info.append(info)

    return {
        "overview": {
            "rows": total_rows,
            "columns": total_cols,
            "cells": total_cells,
            "missing_cells": missing_cells,
            "missing_pct": round(missing_cells / total_cells * 100, 2) if total_cells > 0 else 0,
            "duplicate_rows": duplicate_rows,
            "duplicate_pct": round(duplicate_rows / total_rows * 100, 2) if total_rows > 0 else 0,
            "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
        },
        "columns": columns_info,
    }


def detect_issues(df: pd.DataFrame) -> list[dict]:
    """Detect data quality issues.

    Checks for:
    - High missing-value columns (>30%)
    - Outliers (IQR method) in numeric columns
    - Highly skewed numeric columns (|skew| > 1)
    - Constant columns (single unique value)
    - High cardinality categorical columns (>50 unique values)
    - Duplicate rows

    Args:
        df: Input DataFrame.

    Returns:
        List of issues, each with type, column, severity, and description.
    """
    issues = []
    total_rows = len(df)

    for col in df.columns:
        series = df[col]
        null_pct = series.isna().sum() / total_rows * 100 if total_rows > 0 else 0

        # 1. High missing values
        if null_pct > 30:
            severity = "high" if null_pct > 50 else "medium"
            issues.append({
                "type": "missing_values",
                "column": col,
                "severity": severity,
                "description": f"列 '{col}' 有 {null_pct:.1f}% 的缺失值",
                "detail": {"null_pct": round(null_pct, 1)},
            })

        # 2. Constant columns
        if series.nunique() <= 1 and total_rows > 1:
            issues.append({
                "type": "constant_column",
                "column": col,
                "severity": "medium",
                "description": f"列 '{col}' 是常量列（仅含唯一值），对分析无帮助",
                "detail": {},
            })

        # 3. Numeric column checks
        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()
            if len(clean) < 2:
                continue

            # Outliers (IQR)
            q1 = clean.quantile(0.25)
            q3 = clean.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outlier_count = int(((clean < lower) | (clean > upper)).sum())
                outlier_pct = outlier_count / len(clean) * 100
                if outlier_pct > 5:
                    severity = "high" if outlier_pct > 15 else "medium"
                    issues.append({
                        "type": "outliers",
                        "column": col,
                        "severity": severity,
                        "description": (
                            f"列 '{col}' 有 {outlier_count} 个异常值 "
                            f"({outlier_pct:.1f}%) [IQR={iqr:.2f}]"
                        ),
                        "detail": {
                            "outlier_count": outlier_count,
                            "outlier_pct": round(outlier_pct, 1),
                            "lower_bound": round(float(lower), 2),
                            "upper_bound": round(float(upper), 2),
                        },
                    })

            # Skewness
            skew = float(clean.skew())
            if abs(skew) > 1:
                direction = "右偏（长尾在右）" if skew > 0 else "左偏（长尾在左）"
                severity = "medium" if abs(skew) > 2 else "low"
                issues.append({
                    "type": "skewness",
                    "column": col,
                    "severity": severity,
                    "description": f"列 '{col}' 偏度为 {skew:.2f}，{direction}",
                    "detail": {"skewness": round(skew, 2)},
                })

        # 4. High cardinality for categorical
        if pd.api.types.is_object_dtype(series) or isinstance(series.dtype, pd.CategoricalDtype):
            unique_count = series.nunique()
            if unique_count > 50:
                issues.append({
                    "type": "high_cardinality",
                    "column": col,
                    "severity": "low",
                    "description": f"列 '{col}' 有 {unique_count} 个不同值，基数较高",
                    "detail": {"unique_count": unique_count},
                })

    # 5. Duplicate rows (global)
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        dup_pct = dup_count / total_rows * 100 if total_rows > 0 else 0
        severity = "high" if dup_pct > 10 else "medium"
        issues.append({
            "type": "duplicates",
            "column": None,
            "severity": severity,
            "description": f"数据集有 {dup_count} 行重复数据 ({dup_pct:.1f}%)",
            "detail": {"duplicate_count": dup_count, "duplicate_pct": round(dup_pct, 1)},
        })

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return issues


def generate_profile_report(
    df: pd.DataFrame,
    title: str = "数据分析报告",
    output_path: Optional[str] = None,
) -> str:
    """Generate a ydata-profiling HTML report.

    For large datasets, automatically samples down to MAX_PROFILE_ROWS.

    Args:
        df: Input DataFrame.
        title: Report title.
        output_path: Path to save the HTML report. Auto-generated if None.

    Returns:
        Path to the generated HTML report file.
    """
    from pathlib import Path

    import ydata_profiling

    if output_path is None:
        report_dir = Path("profile_reports")
        report_dir.mkdir(exist_ok=True)
        output_path = str(report_dir / f"profile_{title}.html")  # type: ignore[union-attr]

    # Sample if too large
    if len(df) > MAX_PROFILE_ROWS:
        df_sample = df.sample(n=MAX_PROFILE_ROWS, random_state=42)
        title += f" (采样 {MAX_PROFILE_ROWS:,} / {len(df):,} 行)"
    else:
        df_sample = df

    profile = ydata_profiling.ProfileReport(
        df_sample,
        title=title,
        explorative=True,
        minimal=len(df) > 100_000,
    )
    profile.to_file(output_path)

    return output_path


def get_correlation_matrix(df: pd.DataFrame) -> Optional[dict]:
    """Compute correlation matrix for numeric columns.

    Args:
        df: Input DataFrame.

    Returns:
        dict with column_names and matrix (list of lists), or None if < 2 numeric cols.
    """
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return None

    corr = numeric_df.corr()
    return {
        "columns": list(corr.columns),
        "matrix": corr.round(3).values.tolist(),
    }
