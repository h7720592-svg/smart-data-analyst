"""HTML report builder using Jinja2 templates."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.viz.renderer import figure_to_html

# Template directory
_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "assets"
_DEFAULT_TEMPLATE = "report_template.html"


def _get_jinja_env() -> Environment:
    """Get Jinja2 environment with template loader."""
    if _TEMPLATE_DIR.exists():
        loader = FileSystemLoader(str(_TEMPLATE_DIR))
    else:
        loader = FileSystemLoader(str(Path("assets")))
    return Environment(loader=loader, autoescape=select_autoescape(["html"]))


def build_html_report(
    df_summary: dict,
    df_issues: list[dict],
    figures: list[dict],
    messages: list[dict],
    metadata: dict,
    profile_html_path: Optional[str] = None,
    template_name: str = _DEFAULT_TEMPLATE,
) -> str:
    """Build a complete HTML analysis report.

    Args:
        df_summary: Summary dict from profiler.compute_summary().
        df_issues: Issues list from profiler.detect_issues().
        figures: List of {explanation, figure} dicts from chat history.
        messages: Conversation history.
        metadata: File metadata from data_loader.load_file().
        profile_html_path: Optional path to ydata-profiling HTML.
        template_name: Jinja2 template filename.

    Returns:
        Complete HTML string.
    """
    # Convert Plotly figures to HTML
    chart_sections = []
    for i, fig_data in enumerate(figures):
        try:
            fig_html = figure_to_html(fig_data["figure"])
            chart_sections.append({
                "index": i + 1,
                "title": f"图表 {i + 1}",
                "explanation": fig_data.get("explanation", ""),
                "figure_html": fig_html,
            })
        except Exception:
            chart_sections.append({
                "index": i + 1,
                "title": f"图表 {i + 1}",
                "explanation": fig_data.get("explanation", "图表渲染失败"),
                "figure_html": "<p style='color:red'>图表渲染失败</p>",
            })

    # Build conversation summary
    conversation = []
    for msg in messages:
        role_label = "👤 用户" if msg.get("role") == "user" else "🤖 AI 助手"
        content = msg.get("content", "")
        # Truncate very long messages
        if len(content) > 2000:
            content = content[:2000] + "..."
        conversation.append({
            "role": role_label,
            "content": content,
        })

    # Issues summary
    issues_summary = []
    severity_map = {"high": "严重", "medium": "中等", "low": "轻微"}
    for issue in df_issues:
        issues_summary.append({
            "severity": severity_map.get(issue.get("severity", ""), "提示"),
            "severity_class": issue.get("severity", "low"),
            "description": issue.get("description", ""),
        })

    # Overview metrics
    overview = df_summary.get("overview", {})

    # Read profile HTML if available
    profile_html = None
    if profile_html_path:
        try:
            profile_path = Path(profile_html_path)
            if profile_path.exists():
                profile_html = profile_path.read_text(encoding="utf-8")
        except Exception:
            pass

    # Build template context
    context = {
        "title": f"数据分析报告 - {metadata.get('filename', 'Unknown')}",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metadata": metadata,
        "overview": overview,
        "columns": df_summary.get("columns", []),
        "issues": issues_summary,
        "charts": chart_sections,
        "conversation": conversation,
        "profile_html": profile_html,
        "chart_count": len(chart_sections),
        "issue_count": len(issues_summary),
        "message_count": len(messages),
    }

    try:
        env = _get_jinja_env()
        template = env.get_template(template_name)
        return template.render(**context)
    except Exception:
        # Fallback: generate a simple HTML report without template
        return _build_fallback_report(context)


def _build_fallback_report(context: dict) -> str:
    """Build a simple HTML report when the Jinja2 template is unavailable."""
    # Simple inline CSS
    css = """
    <style>
        body { font-family: 'Microsoft YaHei', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }
        h1 { color: #4F46E5; border-bottom: 2px solid #4F46E5; padding-bottom: 10px; }
        h2 { color: #4F46E5; margin-top: 30px; }
        .meta { color: #888; font-size: 14px; }
        .metrics { display: flex; gap: 15px; flex-wrap: wrap; margin: 20px 0; }
        .metric { background: #F8FAFC; border-radius: 8px; padding: 15px; text-align: center; min-width: 120px; }
        .metric .value { font-size: 24px; font-weight: bold; color: #4F46E5; }
        .metric .label { font-size: 13px; color: #888; }
        .chart-section { margin: 30px 0; border: 1px solid #E2E8F0; border-radius: 8px; padding: 20px; }
        .issue { padding: 8px 12px; margin: 5px 0; border-left: 4px solid #EF4444; background: #FEF2F2; }
        .issue.medium { border-color: #F59E0B; background: #FFFBEB; }
        .issue.low { border-color: #4F46E5; background: #EEF2FF; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 8px 12px; border: 1px solid #E2E8F0; text-align: left; }
        th { background: #F8FAFC; }
    </style>
    """

    # Build metrics HTML
    overview = context.get("overview", {})
    metrics_html = f"""
    <div class="metrics">
        <div class="metric"><div class="value">{overview.get('rows', 0):,}</div><div class="label">行数</div></div>
        <div class="metric"><div class="value">{overview.get('columns', 0)}</div><div class="label">列数</div></div>
        <div class="metric"><div class="value">{overview.get('missing_pct', 0)}%</div><div class="label">缺失值</div></div>
        <div class="metric"><div class="value">{overview.get('duplicate_pct', 0)}%</div><div class="label">重复行</div></div>
        <div class="metric"><div class="value">{overview.get('memory_mb', 0)} MB</div><div class="label">内存</div></div>
    </div>
    """

    # Issues
    issues_html = "".join(
        f'<div class="issue {i.get("severity_class", "low")}">{i["description"]}</div>'
        for i in context.get("issues", [])
    )

    # Charts
    charts_html = "".join(
        f'<div class="chart-section"><h3>{c["title"]}</h3>'
        f'<p>{c["explanation"]}</p>{c["figure_html"]}</div>'
        for c in context.get("charts", [])
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{context['title']}</title>
    {css}
</head>
<body>
    <h1>{context['title']}</h1>
    <p class="meta">生成时间: {context['generated_at']}</p>

    <h2>📊 数据概览</h2>
    {metrics_html}

    <h2>⚠️ 数据问题</h2>
    {issues_html if issues_html else '<p>✅ 未检测到明显问题</p>'}

    <h2>📈 分析图表 ({context['chart_count']})</h2>
    {charts_html if charts_html else '<p>暂无图表</p>'}

    <h2>💬 对话记录 ({context['message_count']} 条消息)</h2>
    {"".join(f'<p><strong>{m["role"]}:</strong> {m["content"][:500]}</p>' for m in context.get("conversation", []))}

    <hr>
    <p class="meta">由 Smart Data Analyst 生成 | 开源项目: github.com/h7720592-svg/smart-data-analyst</p>
</body>
</html>"""


def save_report(html_content: str, output_path: str) -> str:
    """Save HTML report to a file.

    Args:
        html_content: Complete HTML string.
        output_path: File path to save to.

    Returns:
        The output path.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_content, encoding="utf-8")
    return str(path)
