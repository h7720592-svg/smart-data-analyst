"""Chart type registry — defines supported visualization types."""

from typing import Optional

import streamlit as st

# Supported chart types with metadata for the LLM prompt and validation
CHART_TYPES: dict[str, dict] = {
    "bar": {
        "name": "柱状图",
        "function": "px.bar",
        "description": "比较不同类别的数值大小",
        "required_columns": 1,
        "icon": "📊",
    },
    "horizontal_bar": {
        "name": "横向柱状图",
        "function": "px.bar + orientation='h'",
        "description": "类别较多时使用的横向柱状图",
        "required_columns": 1,
        "icon": "📊",
    },
    "line": {
        "name": "折线图",
        "function": "px.line",
        "description": "展示随时间或顺序的变化趋势",
        "required_columns": 2,
        "icon": "📈",
    },
    "scatter": {
        "name": "散点图",
        "function": "px.scatter",
        "description": "展示两个数值变量之间的关系",
        "required_columns": 2,
        "icon": "🎯",
    },
    "pie": {
        "name": "饼图",
        "function": "px.pie",
        "description": "展示各部分占总体的比例",
        "required_columns": 2,
        "icon": "🥧",
    },
    "histogram": {
        "name": "直方图",
        "function": "px.histogram",
        "description": "展示数值变量的分布情况",
        "required_columns": 1,
        "icon": "📶",
    },
    "box": {
        "name": "箱线图",
        "function": "px.box",
        "description": "展示数据分布的四分位数和异常值",
        "required_columns": 1,
        "icon": "📦",
    },
    "heatmap": {
        "name": "热力图",
        "function": "px.imshow",
        "description": "展示矩阵数据（如相关性矩阵）的颜色映射",
        "required_columns": 2,
        "icon": "🔥",
    },
    "area": {
        "name": "面积图",
        "function": "px.area",
        "description": "展示累积趋势，强调数量变化",
        "required_columns": 2,
        "icon": "⛰️",
    },
    "violin": {
        "name": "小提琴图",
        "function": "px.violin",
        "description": "展示不同类别数据的分布形状",
        "required_columns": 2,
        "icon": "🎻",
    },
    "density_heatmap": {
        "name": "密度热力图",
        "function": "px.density_heatmap",
        "description": "展示大量散点的密度分布",
        "required_columns": 2,
        "icon": "🌡️",
    },
    "sunburst": {
        "name": "旭日图",
        "function": "px.sunburst",
        "description": "展示层级数据的比例关系",
        "required_columns": 2,
        "icon": "☀️",
    },
    "treemap": {
        "name": "矩形树图",
        "function": "px.treemap",
        "description": "用矩形面积展示层级数据的比例",
        "required_columns": 2,
        "icon": "🗺️",
    },
    "funnel": {
        "name": "漏斗图",
        "function": "px.funnel",
        "description": "展示各阶段的转化率",
        "required_columns": 2,
        "icon": "🔽",
    },
}


def get_chart_descriptions() -> str:
    """Get a formatted string of chart descriptions for the LLM prompt.

    Returns:
        Multiline string describing all supported chart types.
    """
    lines = []
    for key, info in CHART_TYPES.items():
        lines.append(f"- **{key}** ({info['name']}): {info['description']} — 使用 {info['function']}")
    return "\n".join(lines)


def get_chart_info(chart_type: str) -> Optional[dict]:
    """Get metadata for a specific chart type.

    Args:
        chart_type: Chart type key (e.g., 'bar', 'line').

    Returns:
        Chart info dict or None if not found.
    """
    return CHART_TYPES.get(chart_type)


def display_chart_help() -> None:
    """Display a help panel showing supported chart types."""
    with st.expander("📊 支持的图表类型", expanded=False):
        cols = st.columns(4)
        for i, (key, info) in enumerate(CHART_TYPES.items()):
            with cols[i % 4]:
                st.markdown(
                    f"**{info['icon']} {info['name']}**\n"
                    f"`{key}`\n"
                    f"{info['description']}"
                )
