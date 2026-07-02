"""Data loader module: read CSV, Excel, JSON files with encoding detection."""

import io
import json
from typing import Optional, Tuple

import chardet
import pandas as pd


# Encoding detection order for Chinese CSV files
_ENCODINGS_TO_TRY = ["utf-8", "gbk", "gb2312", "gb18030", "latin-1", "cp1252"]

# Max file size for full read (200MB)
MAX_FILE_SIZE_MB = 200


class DataLoadError(Exception):
    """Raised when data loading fails."""

    pass


def detect_encoding(file_bytes: bytes) -> str:
    """Detect the encoding of a byte string.

    Uses chardet for initial guess, then falls back to trying common
    encodings in order (prioritizing Chinese encodings).

    Args:
        file_bytes: Raw file bytes.

    Returns:
        Detected encoding name (e.g., 'utf-8', 'gbk').
    """
    # Use chardet for initial guess
    result = chardet.detect(file_bytes)
    detected = result.get("encoding", "utf-8")
    confidence = result.get("confidence", 0)

    if detected and confidence > 0.7:
        # Normalize encoding names
        detected_lower = detected.lower()
        if "gb" in detected_lower or detected_lower in ("gb2312", "gbk", "gb18030"):
            return "gbk"
        return detected_lower

    # Low confidence — try encodings in order
    for enc in _ENCODINGS_TO_TRY:
        try:
            file_bytes.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    return "utf-8"  # fallback


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names: strip whitespace, replace special chars."""
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def load_csv(
    file_bytes: bytes,
    encoding: Optional[str] = None,
    separator: Optional[str] = None,
) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame.

    Args:
        file_bytes: Raw CSV file bytes.
        encoding: Encoding to use. Auto-detected if None.
        separator: CSV delimiter. Auto-detected if None.

    Returns:
        pandas DataFrame.

    Raises:
        DataLoadError: If the file cannot be parsed.
    """
    if encoding is None:
        encoding = detect_encoding(file_bytes)

    # Try to detect separator from first line
    if separator is None:
        first_line = file_bytes.decode(encoding, errors="replace").split("\n")[0]
        # Count common delimiters
        delimiters = {",": 0, "\t": 0, ";": 0, "|": 0}
        for char in delimiters:
            delimiters[char] = first_line.count(char)
        separator = max(delimiters, key=delimiters.get)  # type: ignore[arg-type]
        if delimiters[separator] == 0:  # type: ignore[index]
            separator = ","  # default

    errors = []
    for enc in [encoding] + [e for e in _ENCODINGS_TO_TRY if e != encoding]:
        try:
            df = pd.read_csv(
                io.BytesIO(file_bytes),
                encoding=enc,
                sep=separator,
                on_bad_lines="skip",
            )
            df = _normalize_column_names(df)
            return df
        except UnicodeDecodeError:
            errors.append(f"Encoding '{enc}' failed")
            continue
        except pd.errors.ParserError as e:
            errors.append(f"Parser error with '{enc}': {e}")
            continue

    raise DataLoadError(f"Failed to load CSV file: {'; '.join(errors)}")


def load_excel(file_bytes: bytes) -> pd.DataFrame:
    """Load an Excel file (.xlsx or .xls) into a pandas DataFrame.

    Args:
        file_bytes: Raw Excel file bytes.

    Returns:
        pandas DataFrame.

    Raises:
        DataLoadError: If the file cannot be parsed.
    """
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception:
        try:
            # Try legacy .xls format
            df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
        except Exception as e:
            raise DataLoadError(f"Failed to load Excel file: {e}") from e

    df = _normalize_column_names(df)
    return df


def load_json(file_bytes: bytes) -> pd.DataFrame:
    """Load a JSON file into a pandas DataFrame.

    Handles both record-oriented and column-oriented JSON.

    Args:
        file_bytes: Raw JSON file bytes.

    Returns:
        pandas DataFrame.

    Raises:
        DataLoadError: If the file cannot be parsed.
    """
    try:
        data = json.loads(file_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise DataLoadError(f"Failed to parse JSON: {e}") from e

    # Handle different JSON shapes
    if isinstance(data, list):
        # Record-oriented: [{col: val, ...}, ...]
        df = pd.DataFrame(data)
    elif isinstance(data, dict):
        # Check if it's column-oriented: {col: [vals], ...}
        if all(isinstance(v, list) for v in data.values()):
            df = pd.DataFrame(data)
        else:
            # Nested dict — flatten it
            df = pd.json_normalize(data)
    else:
        raise DataLoadError(f"Unsupported JSON structure: {type(data).__name__}")

    df = _normalize_column_names(df)
    return df


def load_file(
    file_bytes: bytes,
    filename: str,
    encoding: Optional[str] = None,
    separator: Optional[str] = None,
) -> Tuple[pd.DataFrame, dict]:
    """Load a data file into a pandas DataFrame.

    Automatically detects file format from extension.

    Args:
        file_bytes: Raw file bytes.
        filename: Original filename (used to detect format).
        encoding: For CSV files, the encoding to use. Auto-detected if None.
        separator: For CSV files, the delimiter. Auto-detected if None.

    Returns:
        Tuple of (DataFrame, metadata_dict).
        metadata contains: filename, file_type, rows, columns, encoding (for CSV),
        column_names, dtypes, memory_mb.

    Raises:
        DataLoadError: If the file cannot be loaded.
        ValueError: If the file type is not supported or file is too large.
    """
    # Check file size
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File too large: {size_mb:.1f}MB. Maximum is {MAX_FILE_SIZE_MB}MB."
        )

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("csv", "tsv", "txt"):
        file_type = "csv"
        df = load_csv(file_bytes, encoding=encoding, separator=separator)
    elif ext in ("xlsx", "xls"):
        file_type = "excel"
        df = load_excel(file_bytes)
    elif ext == "json":
        file_type = "json"
        df = load_json(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file type: .{ext}. "
            f"Supported formats: CSV, Excel (.xlsx/.xls), JSON"
        )

    if df.empty:
        raise DataLoadError("The file contains no data (empty DataFrame).")

    # Build metadata
    metadata = {
        "filename": filename,
        "file_type": file_type,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2),
        "encoding": encoding if file_type == "csv" else None,
    }

    return df, metadata


def get_dataframe_schema_summary(df: pd.DataFrame, max_sample_values: int = 5) -> dict:
    """Build a schema summary for LLM context.

    Args:
        df: The DataFrame to summarize.
        max_sample_values: Max number of sample values per column.

    Returns:
        dict with keys: column_name, dtype, null_count, null_pct,
        unique_count, sample_values.
    """
    schema = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        sample_values = (
            df[col].dropna().head(max_sample_values).tolist()
        )
        # Convert non-serializable types
        sample_values = [
            str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
            for v in sample_values
        ]
        schema.append({
            "column_name": col,
            "dtype": str(df[col].dtype),
            "null_count": null_count,
            "null_pct": round(null_count / len(df) * 100, 1) if len(df) > 0 else 0,
            "unique_count": int(df[col].nunique()),
            "sample_values": sample_values,
        })
    return schema
