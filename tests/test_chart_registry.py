"""Tests for chart_registry module."""

import pytest

from src.viz.chart_registry import (
    CHART_TYPES,
    get_chart_descriptions,
    get_chart_info,
)


class TestChartTypes:
    def test_has_required_charts(self):
        """Verify that core chart types are registered."""
        required = {"bar", "line", "scatter", "pie", "histogram", "box", "heatmap"}
        assert required.issubset(set(CHART_TYPES.keys()))

    def test_minimum_chart_count(self):
        """Should have at least 12 chart types."""
        assert len(CHART_TYPES) >= 12

    def test_all_charts_have_name(self):
        for key, info in CHART_TYPES.items():
            assert "name" in info, f"{key} missing 'name'"
            assert info["name"], f"{key} has empty 'name'"

    def test_all_charts_have_function(self):
        for key, info in CHART_TYPES.items():
            assert "function" in info, f"{key} missing 'function'"

    def test_all_charts_have_description(self):
        for key, info in CHART_TYPES.items():
            assert "description" in info, f"{key} missing 'description'"
            assert info["description"], f"{key} has empty 'description'"

    def test_all_charts_have_icon(self):
        for key, info in CHART_TYPES.items():
            assert "icon" in info, f"{key} missing 'icon'"

    def test_all_charts_have_required_columns(self):
        for key, info in CHART_TYPES.items():
            assert "required_columns" in info, f"{key} missing 'required_columns'"
            assert info["required_columns"] >= 1


class TestGetChartInfo:
    def test_get_existing_chart(self):
        info = get_chart_info("bar")
        assert info is not None
        assert info["name"] == "柱状图"

    def test_get_nonexistent_chart(self):
        info = get_chart_info("nonexistent_chart_type")
        assert info is None

    def test_get_line_chart(self):
        info = get_chart_info("line")
        assert info is not None
        assert "px.line" in info["function"]

    def test_get_all_charts_have_info(self):
        """Every registered chart should return valid info."""
        for chart_type in CHART_TYPES:
            info = get_chart_info(chart_type)
            assert info is not None
            assert info == CHART_TYPES[chart_type]


class TestGetChartDescriptions:
    def test_returns_string(self):
        desc = get_chart_descriptions()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_includes_chart_types(self):
        desc = get_chart_descriptions()
        assert "bar" in desc
        assert "柱状图" in desc
        assert "px.bar" in desc

    def test_includes_all_charts(self):
        desc = get_chart_descriptions()
        for key in CHART_TYPES:
            assert key in desc, f"{key} not found in descriptions"

    def test_is_multiline(self):
        desc = get_chart_descriptions()
        lines = desc.strip().split("\n")
        assert len(lines) >= len(CHART_TYPES)
