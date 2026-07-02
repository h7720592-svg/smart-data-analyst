"""Tests for data_loader module."""

import io
import json

import pandas as pd
import pytest

from src.data_loader import (
    DataLoadError,
    detect_encoding,
    get_dataframe_schema_summary,
    load_csv,
    load_excel,
    load_file,
    load_json,
)


class TestDetectEncoding:
    """Encoding detection tests."""

    def test_detect_utf8(self):
        data = "姓名,年龄\n张三,25\n".encode("utf-8")
        enc = detect_encoding(data)
        assert enc in ("utf-8", "ascii")

    def test_detect_gbk(self):
        data = "姓名,年龄\n张三,25\n".encode("gbk")
        enc = detect_encoding(data)
        # Should detect as gbk or a related Chinese encoding
        assert enc is not None

    def test_detect_ascii(self):
        data = b"name,age\nJohn,25\n"
        enc = detect_encoding(data)
        assert enc is not None  # should return something valid


class TestLoadCSV:
    """CSV loading tests."""

    def test_load_basic_csv(self):
        data = b"name,age,city\nAlice,30,NYC\nBob,25,LA"
        df = load_csv(data)
        assert df.shape == (2, 3)
        assert list(df.columns) == ["name", "age", "city"]

    def test_load_csv_with_chinese(self):
        data = "姓名,年龄,城市\n张三,30,北京\n李四,25,上海".encode("utf-8")
        df = load_csv(data, encoding="utf-8")
        assert df.shape == (2, 3)
        assert df.iloc[0]["姓名"] == "张三"

    def test_load_csv_with_gbk(self):
        data = "姓名,年龄,城市\n张三,30,北京\n".encode("gbk")
        df = load_csv(data, encoding="gbk")
        assert df.shape == (1, 3)
        assert df.iloc[0]["姓名"] == "张三"

    def test_load_csv_auto_detect_separator(self):
        data = b"name;age;city\nAlice;30;NYC\n"
        df = load_csv(data)
        assert df.shape == (1, 3)

    def test_load_empty_csv_raises(self):
        # Empty CSV file; load_csv may return empty df, but load_file should catch it
        data = b""
        with pytest.raises(Exception):
            load_csv(data)

    def test_load_csv_with_missing_values(self):
        data = b"name,age,city\nAlice,,NYC\nBob,25,\n"
        df = load_csv(data)
        assert df.shape == (2, 3)
        assert pd.isna(df.iloc[0]["age"])
        assert pd.isna(df.iloc[1]["city"])

    def test_encoding_fallback(self):
        """Test that when encoding fails, it tries alternatives."""
        data = "姓名,年龄\n张三,30\n".encode("gbk")
        # Provide wrong encoding, it should try fallbacks
        df = load_csv(data, encoding="latin-1")
        # Should still load (may have garbled text, but should not crash)
        assert df.shape[0] >= 1


class TestLoadExcel:
    """Excel loading tests."""

    def test_load_xlsx(self):
        # Create a simple xlsx in memory
        df_in = pd.DataFrame({"name": ["Alice", "Bob"], "age": [30, 25]})
        buffer = io.BytesIO()
        df_in.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)

        df = load_excel(buffer.read())  # type: ignore[arg-type]
        assert df.shape == (2, 2)
        assert list(df.columns) == ["name", "age"]


class TestLoadJSON:
    """JSON loading tests."""

    def test_load_records_json(self):
        data = json.dumps([
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]).encode("utf-8")
        df = load_json(data)
        assert df.shape == (2, 2)

    def test_load_columns_json(self):
        data = json.dumps({
            "name": ["Alice", "Bob"],
            "age": [30, 25],
        }).encode("utf-8")
        df = load_json(data)
        assert df.shape == (2, 2)

    def test_load_invalid_json_raises(self):
        data = b"not valid json"
        with pytest.raises(DataLoadError):
            load_json(data)


class TestLoadFile:
    """load_file integration tests."""

    def test_load_csv_file(self):
        data = b"name,value\nA,10\nB,20"
        df, meta = load_file(data, "test.csv")
        assert df.shape == (2, 2)
        assert meta["filename"] == "test.csv"
        assert meta["file_type"] == "csv"
        assert meta["rows"] == 2
        assert meta["columns"] == 2

    def test_load_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported"):
            load_file(b"test", "test.xyz")

    def test_schema_summary(self):
        data = b"name,age,score\nAlice,30,85.5\nBob,25,92.0"
        df, _ = load_file(data, "test.csv")
        schema = get_dataframe_schema_summary(df)
        assert len(schema) == 3
        assert schema[0]["column_name"] == "name"
        assert schema[1]["dtype"] in ("int64", "Int64")
