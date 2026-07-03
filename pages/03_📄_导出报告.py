"""Page 3: Report generation and export."""

import os
from datetime import datetime

import streamlit as st

from src.export.html_report import build_html_report, save_report
from src.utils import init_session_state

# Ensure exports directory exists
os.makedirs("exports", exist_ok=True)

st.set_page_config(
    page_title="导出报告 - Smart Data Analyst",
    page_icon="📄",
    layout="wide",
)

init_session_state()


def _check_data_ready() -> bool:
    """Check if data and analysis results are available."""
    if st.session_state.get("df") is None:
        st.warning("⚠️ 请先在「📊 数据上传」页面上传数据文件。")
        return False

    if not st.session_state.get("messages"):
        st.info("💡 请先在「💬 智能对话」页面与 AI 对话，生成分析结果后再导出报告。")
        return False

    return True


# ── Main Content ─────────────────────────────────────────────────────────
st.title("📄 导出分析报告")
st.caption("将分析结果导出为 HTML 或 PDF 格式的报告")

if not _check_data_ready():
    st.stop()

# ── Report Preview ──────────────────────────────────────────────────────
st.subheader("📋 报告内容预览")

df = st.session_state["df"]
metadata = st.session_state.get("df_metadata", {})
df_summary = st.session_state.get("df_summary", {})
df_issues = st.session_state.get("df_issues", [])
messages = st.session_state.get("messages", [])
figures = st.session_state.get("figures", [])
profile_report_path = st.session_state.get("profile_report_path")

# Display report summary
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("数据行数", f"{metadata.get('rows', 0):,}")
with col2:
    st.metric("数据列数", metadata.get("columns", 0))
with col3:
    st.metric("图表数量", len(figures))
with col4:
    st.metric("对话轮次", len(messages))

# Issues summary
if df_issues:
    st.subheader("⚠️ 包含的数据质量问题")
    for issue in df_issues[:5]:
        severity_icon = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(
            issue.get("severity", ""), "ℹ️"
        )
        st.markdown(f"- {severity_icon} {issue['description']}")
    if len(df_issues) > 5:
        st.caption(f"... 还有 {len(df_issues) - 5} 个问题")

# Charts preview
if figures:
    st.subheader("📈 包含的图表")
    for i, fig_data in enumerate(figures):
        st.markdown(f"**图表 {i + 1}**: {fig_data.get('explanation', '无描述')[:100]}")

# ── Export Options ──────────────────────────────────────────────────────
st.divider()
st.subheader("📥 导出选项")

export_format = st.radio(
    "选择导出格式",
    options=["html", "pdf"],
    format_func=lambda x: {"html": "HTML（可在浏览器中查看，图表可交互）", "pdf": "PDF（适合打印和分享）"}[x],
    horizontal=True,
)

include_sections = st.multiselect(
    "选择报告包含的内容",
    options=["overview", "columns", "issues", "charts", "conversation"],
    default=["overview", "columns", "issues", "charts"],
    format_func=lambda x: {
        "overview": "数据概览",
        "columns": "列详情",
        "issues": "数据问题",
        "charts": "分析图表",
        "conversation": "对话记录",
    }[x],
)

# ── Generate Report ─────────────────────────────────────────────────────
if st.button("🔨 生成报告", type="primary", use_container_width=True):
    with st.spinner("正在生成报告..."):
        try:
            # Filter data based on user selection
            report_figures = figures if "charts" in include_sections else []
            report_issues = df_issues if "issues" in include_sections else []
            report_messages = messages if "conversation" in include_sections else []
            report_summary = df_summary if "overview" in include_sections else {}

            if "overview" not in include_sections and df_summary:
                report_summary = {"overview": df_summary.get("overview", {}), "columns": []}
            if "columns" not in include_sections:
                report_summary = {
                    "overview": report_summary.get("overview", {}),
                    "columns": [],
                }

            # Build HTML report
            html_content = build_html_report(
                df_summary=report_summary,
                df_issues=report_issues,
                figures=report_figures,
                messages=report_messages,
                metadata=metadata,
                profile_html_path=profile_report_path
                if "overview" in include_sections
                else None,
            )

            # Generate filename
            base_name = metadata.get("filename", "data").rsplit(".", 1)[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if export_format == "html":
                output_path = f"exports/report_{base_name}_{timestamp}.html"
                save_report(html_content, output_path)

                # Provide download
                with open(output_path, "r", encoding="utf-8") as f:
                    st.download_button(
                        label="📥 下载 HTML 报告",
                        data=f.read(),
                        file_name=f"report_{base_name}.html",
                        mime="text/html",
                        use_container_width=True,
                    )

                st.success(f"✅ HTML 报告已生成！保存在: `{output_path}`")

                # Preview
                with st.expander("👁️ 预览 HTML 报告", expanded=True):
                    st.components.v1.html(html_content, height=600, scrolling=True)

            elif export_format == "pdf":
                # First save HTML, then convert to PDF
                html_path = f"exports/report_{base_name}_{timestamp}.html"
                pdf_path = f"exports/report_{base_name}_{timestamp}.pdf"
                save_report(html_content, html_path)

                try:
                    from src.export.pdf_report import html_to_pdf

                    html_to_pdf(html_content, pdf_path)

                    # Provide download
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="📥 下载 PDF 报告",
                            data=f.read(),
                            file_name=f"report_{base_name}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )

                    st.success(f"✅ PDF 报告已生成！保存在: `{pdf_path}`")

                except ImportError:
                    st.warning(
                        "⚠️ 需要安装 WeasyPrint 才能导出 PDF。\n\n"
                        "请运行: `pip install weasyprint`\n\n"
                        "已为您生成 HTML 版本作为替代。"
                    )
                    with open(html_path, "r", encoding="utf-8") as f:
                        st.download_button(
                            label="📥 下载 HTML 报告（替代 PDF）",
                            data=f.read(),
                            file_name=f"report_{base_name}.html",
                            mime="text/html",
                            use_container_width=True,
                        )
                except Exception as e:
                    st.error(f"PDF 生成失败: {e}")
                    st.info("已为您生成 HTML 版本作为替代。")
                    with open(html_path, "r", encoding="utf-8") as f:
                        st.download_button(
                            label="📥 下载 HTML 报告（替代 PDF）",
                            data=f.read(),
                            file_name=f"report_{base_name}.html",
                            mime="text/html",
                            use_container_width=True,
                        )

        except Exception as e:
            st.error(f"报告生成失败: {e}")
