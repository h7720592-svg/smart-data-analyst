"""Plotly figure renderer for Streamlit."""

from typing import Optional

import plotly.graph_objects as go
import streamlit as st
from plotly.basedatatypes import BaseFigure


# Consistent chart theme
CHART_THEME = {
    "template": "plotly_white",
    "font_family": "Inter, Microsoft YaHei, sans-serif",
    "title_font_size": 18,
    "colorway": [
        "#4F46E5", "#10B981", "#F59E0B", "#EF4444",
        "#8B5CF6", "#06B6D4", "#F97316", "#EC4899",
        "#6366F1", "#14B8A6",
    ],
}


def apply_theme(fig: BaseFigure) -> BaseFigure:
    """Apply consistent theme to a Plotly figure.

    Args:
        fig: Plotly figure object.

    Returns:
        The same figure with theme applied (mutated in place).
    """
    fig.update_layout(
        template=CHART_THEME["template"],
        font=dict(family=CHART_THEME["font_family"]),
        title=dict(
            font=dict(size=CHART_THEME["title_font_size"]),
        ),
        colorway=CHART_THEME["colorway"],
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )
    return fig


def render_figure(
    fig: BaseFigure,
    use_container_width: bool = True,
    height: Optional[int] = None,
) -> None:
    """Render a Plotly figure in Streamlit with consistent theming.

    Args:
        fig: Plotly figure object (px or go Figure).
        use_container_width: Whether to use full container width.
        height: Optional chart height in pixels.
    """
    try:
        fig = apply_theme(fig)

        if height:
            fig.update_layout(height=height)

        st.plotly_chart(
            fig,
            use_container_width=use_container_width,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": "chart",
                    "scale": 2,
                },
            },
        )
    except Exception as e:
        st.error(f"图表渲染失败: {e}")
        # Try fallback — just show the figure without theme
        try:
            st.plotly_chart(fig, use_container_width=use_container_width)
        except Exception:
            st.error("图表无法渲染，请尝试换一种提问方式。")


def figure_to_html(fig: BaseFigure) -> str:
    """Convert a Plotly figure to an HTML string (for reports).

    Args:
        fig: Plotly figure object.

    Returns:
        HTML string with embedded Plotly chart.
    """
    fig = apply_theme(fig)
    return fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config={
            "displayModeBar": False,
            "displaylogo": False,
            "responsive": True,
        },
    )


def figure_to_image_bytes(fig: BaseFigure, format: str = "png", scale: int = 2) -> bytes:
    """Convert a Plotly figure to image bytes (for PDF export).

    Args:
        fig: Plotly figure object.
        format: Image format ('png', 'svg', 'jpeg', 'pdf').
        scale: Image scale factor.

    Returns:
        Image bytes.

    Raises:
        RuntimeError: If kaleido is not installed.
    """
    try:
        fig = apply_theme(fig)
        img_bytes: bytes = fig.to_image(format=format, scale=scale)
        return img_bytes
    except ValueError as e:
        if "kaleido" in str(e).lower():
            raise RuntimeError(
                "需要安装 kaleido 才能导出图片。请运行: pip install kaleido"
            ) from e
        raise
