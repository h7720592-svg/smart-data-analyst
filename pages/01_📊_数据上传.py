"""Page 1: File upload, data preview, and auto-profiling."""

import time

import pandas as pd
import streamlit as st

from src.data_loader import get_dataframe_schema_summary, load_file
from src.profiler import compute_summary, detect_issues, generate_profile_report
from src.utils import format_number, init_session_state

st.set_page_config(
    page_title="数据上传 - Smart Data Analyst",
    page_icon="📊",
    layout="wide",
)

init_session_state()


def _render_metrics(summary: dict) -> None:
    """Render overview metric cards."""
    overview = summary["overview"]
    cols = st.columns(6)
    metrics = [
        ("行数", format_number(overview["rows"]), "📋"),
        ("列数", overview["columns"], "📌"),
        ("缺失值", f"{overview['missing_pct']}%", "❓"),
        ("重复行", f"{overview['duplicate_pct']}%", "🔄"),
        ("内存", f"{overview['memory_mb']} MB", "💾"),
        ("数据质量", _quality_score(summary), "✅"),
    ]
    for i, (label, value, icon) in enumerate(metrics):
        with cols[i]:
            st.markdown(
                f"""<div class="metric-card">
                    <div style="font-size:20px;">{icon}</div>
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def _quality_score(summary: dict) -> str:
    """Compute a simple data quality score."""
    overview = summary["overview"]
    # Score based on missing values and duplicates
    missing_penalty = min(overview["missing_pct"] / 10, 3)
    dup_penalty = min(overview["duplicate_pct"] / 5, 2)
    score = max(1, 10 - missing_penalty - dup_penalty)
    stars = "⭐" * int(score)
    return stars


def _render_issues(issues: list[dict]) -> None:
    """Render detected data issues."""
    if not issues:
        st.success("🎉 未检测到明显的数据质量问题！")
        return

    severity_labels = {"high": "🔴 严重", "medium": "🟡 中等", "low": "🔵 轻微"}
    severity_map = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "info": "low",
    }

    st.warning(f"检测到 **{len(issues)}** 个潜在问题：")

    for issue in issues:
        sev = issue.get("severity", "info")
        sev_class = severity_map.get(sev, "low")
        label = severity_labels.get(sev, "ℹ️ 提示")
        st.markdown(
            f"""<div class="issue-card severity-{sev_class}">
                <strong>{label}</strong> — {issue['description']}
            </div>""",
            unsafe_allow_html=True,
        )


def _render_column_table(summary: dict) -> None:
    """Render per-column details in an expandable table."""
    with st.expander("📋 查看列详情", expanded=False):
        col_data = []
        for c in summary["columns"]:
            row = {
                "列名": c["name"],
                "类型": c["dtype"],
                "缺失": f"{c['null_pct']}%",
                "唯一值": c["unique_count"],
            }
            if "mean" in c and c["mean"] is not None:
                row["均值"] = c["mean"]
                row["标准差"] = c["std"]
                row["最小"] = c["min"]
                row["最大"] = c["max"]
            if "top_values" in c:
                top_str = ", ".join(
                    f"{k}({v})" for k, v in list(c["top_values"].items())[:3]
                )
                row["常见值"] = top_str
            col_data.append(row)
        st.dataframe(
            pd.DataFrame(col_data),
            use_container_width=True,
            hide_index=True,
        )


# ── Sidebar: LLM Configuration ──────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ API 配置")
    st.caption("配置 AI 模型以启用智能对话功能")

    provider = st.selectbox(
        "LLM 提供商",
        options=["deepseek", "openai", "groq", "ollama", "custom"],
        format_func=lambda x: {
            "deepseek": "DeepSeek (推荐)",
            "openai": "OpenAI",
            "groq": "Groq",
            "ollama": "Ollama (本地)",
            "custom": "自定义",
        }.get(x, x),
        index=0,
    )
    st.session_state["llm_provider"] = provider

    model_options = {
        "deepseek": ["deepseek-v4-flash"],
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"],
        "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "ollama": ["llama3", "qwen2.5", "mistral"],
        "custom": [],
    }
    models = model_options.get(provider, [])

    if provider == "custom":
        model = st.text_input("模型名称", value="gpt-4o-mini")
        base_url = st.text_input(
            "API Base URL",
            value=st.session_state.get("llm_base_url", ""),
            placeholder="https://api.example.com/v1",
        )
        st.session_state["llm_base_url"] = base_url
    else:
        model = st.selectbox("模型", options=models, index=0)

    st.session_state["llm_model"] = model

    # Thinking mode toggle (DeepSeek only)
    if provider == "deepseek":
        thinking = st.checkbox(
            "🧠 深度思考模式",
            value=st.session_state.get("llm_thinking", False),
            help="启用后 AI 会进行更深度的推理，适合复杂分析问题，但响应较慢。"
        )
        st.session_state["llm_thinking"] = thinking

    api_key = st.text_input(
        "API Key",
        type="password",
        value=st.session_state.get("llm_api_key", ""),
        placeholder=f"输入 {provider.upper()}_API_KEY",
    )
    st.session_state["llm_api_key"] = api_key

    st.divider()
    st.caption(
        "💡 提示：API Key 仅存储在会话中，不会被上传或共享。\n\n"
        "DeepSeek API Key 获取：https://platform.deepseek.com"
    )

# ── Main Content ─────────────────────────────────────────────────────────
st.title("📊 智能数据分析助手")
st.caption("上传您的数据文件，AI 将自动分析并生成可视化报告")

# File upload
uploaded_file = st.file_uploader(
    "选择数据文件",
    type=["csv", "xlsx", "xls", "json"],
    help="支持 CSV、Excel (.xlsx/.xls)、JSON 格式，最大 200MB",
)

# Manual encoding option for CSV
if uploaded_file is not None and uploaded_file.name.endswith(".csv"):
    enc_col1, enc_col2 = st.columns([3, 1])
    with enc_col1:
        st.caption(
            "如中文乱码，请手动选择编码。常用：UTF-8 / GBK / GB2312 / GB18030"
        )
    with enc_col2:
        manual_encoding = st.selectbox(
            "编码",
            options=["auto", "utf-8", "gbk", "gb2312", "gb18030", "latin-1"],
            index=0,
            label_visibility="collapsed",
        )
else:
    manual_encoding = "auto"

if uploaded_file is not None:
    file_bytes = uploaded_file.read()

    # Check if file changed
    file_key = f"{uploaded_file.name}_{len(file_bytes)}"
    if st.session_state.get("_last_file_key") != file_key:
        st.session_state["_last_file_key"] = file_key
        # Reset data state
        st.session_state["df"] = None
        st.session_state["df_metadata"] = None
        st.session_state["df_schema"] = None
        st.session_state["df_summary"] = None
        st.session_state["df_issues"] = None
        st.session_state["profile_report_path"] = None
        st.session_state["messages"] = []
        st.session_state["figures"] = []

    try:
        with st.spinner("正在加载文件..."):
            encoding = None if manual_encoding == "auto" else manual_encoding
            df, metadata = load_file(
                file_bytes, uploaded_file.name, encoding=encoding
            )
            st.session_state["df"] = df
            st.session_state["df_metadata"] = metadata
            st.session_state["df_schema"] = get_dataframe_schema_summary(df)
            # Compute summary and issues
            st.session_state["df_summary"] = compute_summary(df)
            st.session_state["df_issues"] = detect_issues(df)

        st.success(
            f"✅ 文件加载成功！{metadata['rows']:,} 行 × {metadata['columns']} 列"
        )

        # ── Tabs for different views ──
        tab1, tab2, tab3 = st.tabs(["📋 数据预览", "📊 数据画像", "⚠️ 数据问题"])

        with tab1:
            st.subheader("数据预览（前 100 行）")
            st.dataframe(
                df.head(100),
                use_container_width=True,
                height=400,
            )

        with tab2:
            st.subheader("数据概览")
            summary = st.session_state["df_summary"]
            _render_metrics(summary)
            _render_column_table(summary)

            # Correlation analysis
            from src.profiler import get_correlation_matrix

            corr = get_correlation_matrix(df)
            if corr:
                with st.expander("🔗 相关性分析", expanded=False):
                    import plotly.express as px

                    fig = px.imshow(
                        corr["matrix"],
                        x=corr["columns"],
                        y=corr["columns"],
                        color_continuous_scale="RdBu_r",
                        zmin=-1,
                        zmax=1,
                        title="相关性热力图",
                    )
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, use_container_width=True)

            # Generate full profile report
            if st.button("🔬 生成完整数据画像报告", type="primary"):
                with st.spinner("正在生成数据画像报告（可能需要 1-2 分钟）..."):
                    try:
                        title = uploaded_file.name.rsplit(".", 1)[0]
                        report_path = generate_profile_report(
                            df, title=title
                        )
                        st.session_state["profile_report_path"] = report_path
                        st.success("报告生成成功！")
                    except Exception as e:
                        st.error(f"生成报告时出错：{e}")

            if st.session_state.get("profile_report_path"):
                report_path = st.session_state["profile_report_path"]
                with open(report_path, "r", encoding="utf-8") as f:
                    report_html = f.read()
                st.download_button(
                    "📥 下载数据画像报告 (HTML)",
                    data=report_html,
                    file_name=f"profile_{uploaded_file.name}.html",
                    mime="text/html",
                )

        with tab3:
            st.subheader("数据质量问题")
            issues = st.session_state.get("df_issues", [])
            _render_issues(issues)

        # Navigation hint
        st.divider()
        col_a, col_b = st.columns([3, 1])
        with col_a:
            if st.session_state.get("llm_api_key"):
                st.info(
                    "💡 数据已就绪！切换到 **💬 智能对话** 页面开始使用 AI 分析数据。"
                )
            else:
                st.warning(
                    "⚠️ 请在左侧配置 API Key，然后在 **💬 智能对话** 页面使用 AI 功能。"
                )

    except Exception as e:
        st.error(f"❌ 加载文件失败：{e}")
        st.info("请检查文件格式和编码，或尝试手动选择编码。")

else:
    # Empty state — show instructions
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
        ### 📁 支持格式
        - **CSV** (.csv)
        - **Excel** (.xlsx, .xls)
        - **JSON** (.json)
        """
        )
    with col2:
        st.markdown(
            """
        ### 🔍 自动分析
        - 数据概览与统计
        - 缺失值检测
        - 异常值检测 (IQR)
        - 相关性分析
        """
        )
    with col3:
        st.markdown(
            """
        ### 🤖 AI 功能
        - 自然语言提问
        - 自动生成图表
        - 数据洞察解释
        - 报告导出
        """
        )
