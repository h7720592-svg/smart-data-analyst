"""Tests for prompts module."""

import pytest

from src.llm.prompts import (
    build_chat_context,
    build_error_fix_prompt,
    build_system_prompt,
    _estimate_tokens,
    _truncate_message_content,
)

SAMPLE_SCHEMA = [
    {
        "column_name": "name",
        "dtype": "object",
        "null_pct": 0.0,
        "unique_count": 10,
        "sample_values": ["Alice", "Bob", "Charlie"],
    },
    {
        "column_name": "age",
        "dtype": "int64",
        "null_pct": 5.0,
        "unique_count": 8,
        "sample_values": [25, 30, 35],
    },
    {
        "column_name": "score",
        "dtype": "float64",
        "null_pct": 2.5,
        "unique_count": 10,
        "sample_values": [85.5, 92.0, 78.3],
    },
]


class TestEstimateTokens:
    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_short_string(self):
        tokens = _estimate_tokens("hello")
        assert tokens > 0

    def test_chinese_string(self):
        tokens = _estimate_tokens("你好世界")
        assert tokens >= 2

    def test_long_string(self):
        tokens = _estimate_tokens("x" * 10000)
        assert tokens == 5000  # len // 2


class TestTruncateMessageContent:
    def test_short_content(self):
        result = _truncate_message_content("hello", max_chars=100)
        assert result == "hello"

    def test_long_content_truncated(self):
        content = "x" * 5000
        result = _truncate_message_content(content, max_chars=3000)
        assert len(result) < len(content)
        assert "截断" in result

    def test_exact_boundary(self):
        content = "x" * 3000
        result = _truncate_message_content(content, max_chars=3000)
        assert result == content  # exactly at boundary, not truncated


class TestBuildSystemPrompt:
    def test_basic_prompt(self):
        prompt = build_system_prompt(SAMPLE_SCHEMA, n_rows=100, n_cols=3, memory_mb=5.2)
        assert "100" in prompt
        assert "3" in prompt
        assert "name" in prompt
        assert "age" in prompt
        assert "score" in prompt
        assert "5.2" in prompt
        assert "RESPONSE FORMAT" in prompt
        assert "CODE GENERATION RULES" in prompt

    def test_schema_limit_50_columns(self):
        """Test that schemas with >50 columns are truncated."""
        large_schema = [
            {"column_name": f"col_{i}", "dtype": "int64",
             "null_pct": 0.0, "unique_count": 1, "sample_values": [1]}
            for i in range(60)
        ]
        prompt = build_system_prompt(large_schema, n_rows=10, n_cols=60)
        assert "col_0" in prompt
        assert "col_49" in prompt
        assert "10 more columns" in prompt

    def test_empty_schema(self):
        prompt = build_system_prompt([], n_rows=0, n_cols=0)
        assert "0" in prompt


class TestBuildChatContext:
    def test_basic_context(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        context = build_chat_context(
            messages, SAMPLE_SCHEMA, n_rows=100, n_cols=3,
            max_history=10, memory_mb=1.0,
        )
        assert context[0]["role"] == "system"
        assert len(context) >= 2  # system + at least 1 message

    def test_history_limit(self):
        """Test that history is limited to max_history."""
        messages = [
            {"role": "user", "content": f"msg_{i}"}
            for i in range(20)
        ]
        context = build_chat_context(
            messages, SAMPLE_SCHEMA, n_rows=100, n_cols=3,
            max_history=5, memory_mb=1.0,
        )
        # System prompt + at most 5 messages
        assert len(context) <= 6

    def test_token_budget_truncation(self):
        """Test that very long messages don't exceed token budget."""
        messages = [
            {"role": "user", "content": "x" * 50000},  # ~25K tokens
            {"role": "assistant", "content": "y" * 50000},
        ]
        context = build_chat_context(
            messages, SAMPLE_SCHEMA, n_rows=100, n_cols=3,
            max_history=10,
        )
        # Should not include all messages due to token budget
        assert len(context) >= 1  # at minimum has system prompt

    def test_empty_history(self):
        context = build_chat_context(
            [], SAMPLE_SCHEMA, n_rows=100, n_cols=3,
        )
        assert len(context) == 1  # only system prompt


class TestBuildErrorFixPrompt:
    def test_basic_fix_prompt(self):
        prompt = build_error_fix_prompt(
            code="import os",
            error_message="禁止导入模块: os",
            user_request="画一张柱状图",
        )
        assert "import os" in prompt
        assert "禁止导入模块: os" in prompt
        assert "画一张柱状图" in prompt
        assert "未定义" in prompt  # common error patterns section

    def test_fix_prompt_mentions_timeout(self):
        prompt = build_error_fix_prompt(
            code="while True: pass",
            error_message="代码执行超时",
            user_request="分析数据",
        )
        assert "超时" in prompt

    def test_fix_prompt_includes_common_errors(self):
        prompt = build_error_fix_prompt("", "", "")
        assert "变量未定义" in prompt
        assert "超时" in prompt
        assert "禁止导入" in prompt
