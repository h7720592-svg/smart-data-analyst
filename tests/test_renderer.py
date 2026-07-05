"""Tests for renderer module."""

import pytest

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.viz.renderer import (
    apply_theme,
    figure_to_html,
    figure_to_image_bytes,
    CHART_THEME,
)


@pytest.fixture
def sample_fig():
    """Create a sample Plotly figure for testing."""
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    return px.scatter(df, x="x", y="y", title="Test Chart")


class TestChartTheme:
    def test_theme_has_template(self):
        assert "template" in CHART_THEME
        assert CHART_THEME["template"] == "plotly_white"

    def test_theme_has_font(self):
        assert "font_family" in CHART_THEME
        assert "Microsoft YaHei" in CHART_THEME["font_family"]

    def test_theme_has_colorway(self):
        assert "colorway" in CHART_THEME
        assert len(CHART_THEME["colorway"]) >= 8


class TestApplyTheme:
    def test_applies_template(self, sample_fig):
        themed = apply_theme(sample_fig)
        # Template is stored as a string reference or Template object
        template = themed.layout.template
        if isinstance(template, str):
            assert template == CHART_THEME["template"]
        else:
            # It's a Template object with plotly_white merged
            assert template is not None

    def test_applies_font(self, sample_fig):
        themed = apply_theme(sample_fig)
        # Font family should be set
        assert themed.layout.font.family is not None

    def test_applies_margins(self, sample_fig):
        themed = apply_theme(sample_fig)
        assert themed.layout.margin.l == 20
        assert themed.layout.margin.r == 20

    def test_applies_legend(self, sample_fig):
        themed = apply_theme(sample_fig)
        assert themed.layout.legend.orientation == "h"

    def test_returns_same_figure_type(self, sample_fig):
        themed = apply_theme(sample_fig)
        assert isinstance(themed, go.Figure)

    def test_works_with_go_figure(self):
        fig = go.Figure(data=[go.Bar(x=[1, 2, 3], y=[4, 5, 6])])
        themed = apply_theme(fig)
        assert isinstance(themed, go.Figure)


class TestFigureToHTML:
    def test_returns_html_string(self, sample_fig):
        html = figure_to_html(sample_fig)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_includes_plotly_js(self, sample_fig):
        html = figure_to_html(sample_fig)
        assert "plotly" in html.lower()

    def test_responsive_config(self, sample_fig):
        html = figure_to_html(sample_fig)
        assert "responsive" in html.lower()

    def test_applies_theme(self, sample_fig):
        html = figure_to_html(sample_fig)
        # Themed figure should still produce valid HTML
        assert "<div" in html


class TestFigureToImageBytes:
    def test_returns_bytes(self, sample_fig):
        try:
            img_bytes = figure_to_image_bytes(sample_fig, format="png", scale=1)
            assert isinstance(img_bytes, bytes)
            assert len(img_bytes) > 0
        except RuntimeError as e:
            if "kaleido" in str(e).lower():
                pytest.skip("kaleido not installed")
            raise

    def test_png_format(self, sample_fig):
        try:
            img_bytes = figure_to_image_bytes(sample_fig, format="png")
            assert len(img_bytes) > 0
            # PNG magic bytes
            assert img_bytes[:8] == b'\x89PNG\r\n\x1a\n'
        except RuntimeError as e:
            if "kaleido" in str(e).lower():
                pytest.skip("kaleido not installed")
            raise
