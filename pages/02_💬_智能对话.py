"""Page 2: Natural language chat with AI data analysis."""

import logging

import streamlit as st

from src.llm.client import create_client_from_config
from src.llm.code_executor import execute, ExecutionResult
from src.llm.prompts import build_chat_context, build_error_fix_prompt
from src.utils import init_session_state
from src.viz.chart_registry import display_chart_help
from src.viz.renderer import render_figure

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="智能对话 - Smart Data Analyst",
    page_icon="💬",
    layout="wide",
)

init_session_state()


def _execute_chart_code(code: str) -> ExecutionResult:
    """Execute chart generation code.

    Args:
        code: Python code string from LLM.

    Returns:
        ExecutionResult with Figure objects.
    """
    df = st.session_state.get("df")
    if df is None:
        return ExecutionResult(
            success=False, error="数据未加载，请先上传数据文件。", error_type="NoData"
        )

    return execute(code, df)


def _handle_llm_result(result: dict, container) -> None:
    """Handle a parsed LLM response and render the result.

    Args:
        result: Parsed response dict with type/code/explanation.
        container: Streamlit container to render into.
    """
    response_type = result.get("type", "text")
    explanation = result.get("explanation", "")
    code = result.get("code", "")

    if response_type in ("chart", "chart+text"):
        if code:
            with st.spinner("🔧 正在生成图表..."):
                exec_result = _execute_chart_code(code)

            if exec_result.success and exec_result.figures:
                for fig in exec_result.figures:
                    render_figure(fig)
                    # Save figure for report
                    if "figures" not in st.session_state:
                        st.session_state["figures"] = []
                    st.session_state["figures"].append({
                        "explanation": explanation,
                        "figure": fig,
                    })

                if explanation:
                    st.markdown(explanation)
            else:
                # Execution failed — show error and try auto-fix
                error_msg = exec_result.error or "未知错误"
                st.error(f"图表生成失败: {error_msg}")

                # Show generated code for debugging
                if code:
                    with st.expander("🔍 查看生成的代码"):
                        st.code(code, language="python")

                if exec_result.stdout:
                    with st.expander("🔍 查看执行输出"):
                        st.text(exec_result.stdout)

                # Auto-retry with error feedback (only if it's not a timeout)
                if "超时" not in error_msg:
                    with st.spinner("🔄 正在尝试修正..."):
                        _auto_fix_and_retry(code, error_msg, container)
                else:
                    st.warning("💡 提示：代码执行超时。请尝试换一种更具体的提问方式，例如：\n\n- \"画一张各地区销售额的柱状图\"\n- \"显示月度销售趋势\"\n- \"分析产品类别的利润分布\"")
        elif explanation:
            st.markdown(explanation)

    elif response_type == "text":
        if explanation:
            st.markdown(explanation)
        else:
            st.markdown(str(result))


def _auto_fix_and_retry(code: str, error_msg: str, container) -> None:
    """Attempt to auto-fix broken code by asking LLM to correct it.

    Args:
        code: The broken code.
        error_msg: The error message.
        container: Streamlit container for rendering fixed result.
    """
    df = st.session_state.get("df")
    if df is None:
        return

    # Build the user's original request from chat history
    messages = st.session_state.get("messages", [])
    user_request = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_request = msg.get("content", "")
            break

    # Build fix prompt with data schema context
    schema = st.session_state.get("df_schema", [])
    metadata = st.session_state.get("df_metadata", {})
    fix_prompt = build_error_fix_prompt(
        code, error_msg, user_request,
        schema=schema,
        n_rows=len(df),
        n_cols=len(df.columns),
    )
    fix_messages = [{"role": "user", "content": fix_prompt}]

    try:
        config = {
            "provider": st.session_state.get("llm_provider", "deepseek"),
            "model": st.session_state.get("llm_model", "deepseek-v4-flash"),
            "api_key": st.session_state.get("llm_api_key", ""),
            "base_url": st.session_state.get("llm_base_url", ""),
        }
        client = create_client_from_config(config)
        result = client.chat_structured(
            messages=fix_messages, temperature=0.1, max_tokens=16384
        )
        fixed_code = result.get("code", "")
        fixed_explanation = result.get("explanation", "已自动修正代码。")

        if fixed_code:
            exec_result = _execute_chart_code(fixed_code)
            if exec_result.success and exec_result.figures:
                st.success("✅ 已自动修正并成功生成图表")
                for fig in exec_result.figures:
                    render_figure(fig)
                    # Save to session state for persistence and report export
                    if "figures" not in st.session_state:
                        st.session_state["figures"] = []
                    st.session_state["figures"].append({
                        "explanation": fixed_explanation,
                        "figure": fig,
                    })
                if fixed_explanation:
                    st.markdown(fixed_explanation)
            else:
                st.error(f"自动修正失败: {exec_result.error}")

    except Exception as e:
        st.info(f"自动修正不可用: {e}")


def _process_user_message(user_input: str) -> dict:
    """Process a user message and generate an AI response.

    Args:
        user_input: The user's text input.

    Returns:
        Parsed response dict with type/code/explanation.
    """
    df = st.session_state.get("df")
    if df is None:
        return {
            "type": "text",
            "explanation": "⚠️ 请先在「📊 数据上传」页面上传数据文件，然后再使用对话功能。",
        }

    schema = st.session_state.get("df_schema", [])
    metadata = st.session_state.get("df_metadata", {})

    # Build chat context
    messages = build_chat_context(
        messages=st.session_state.get("messages", []),
        schema=schema,
        n_rows=len(df),
        n_cols=len(df.columns),
        max_history=10,
        memory_mb=metadata.get("memory_mb", 0),
    )

    # Add the new user message
    messages.append({"role": "user", "content": user_input})

    # Call LLM
    config = {
        "provider": st.session_state.get("llm_provider", "deepseek"),
        "model": st.session_state.get("llm_model", "deepseek-v4-flash"),
        "api_key": st.session_state.get("llm_api_key", ""),
        "base_url": st.session_state.get("llm_base_url", ""),
        "thinking": st.session_state.get("llm_thinking", False),
    }

    try:
        client = create_client_from_config(config)

        with st.spinner("🤔 AI 正在思考..."):
            result = client.chat_structured(
                messages=messages, temperature=0.1, max_tokens=16384
            )

        return result

    except ValueError as e:
        error_str = str(e)
        if "API Key" in error_str:
            return {"type": "text", "explanation": "⚠️ 请先在「📊 数据上传」页面的侧边栏配置 API Key。"}
        # JSON parse failure — try to use the raw response as text
        if "无法解析" in error_str:
            # Extract the raw text from the error message for display
            raw_preview = error_str.split("原始响应（前800字符）:\n")[-1] if "原始响应" in error_str else ""
            return {
                "type": "text",
                "explanation": f"⚠️ AI 返回了非标准格式的响应。以下是原始回复:\n\n{raw_preview}",
            }
        raise
    except Exception as e:
        return {
            "type": "text",
            "explanation": f"❌ AI 服务调用失败: {e}\n\n请检查 API Key 和网络连接。",
        }


# ── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("💬 对话设置")

    # Data status
    df = st.session_state.get("df")
    if df is not None:
        metadata = st.session_state.get("df_metadata", {})
        st.success(f"📁 已加载: **{metadata.get('filename', 'N/A')}**")
        st.caption(f"{len(df):,} 行 × {len(df.columns)} 列")
    else:
        st.warning("⚠️ 未加载数据文件")
        st.caption("请先到「📊 数据上传」页面上传文件")

    st.divider()

    # Chart type help
    display_chart_help()

    st.divider()

    # Clear chat button
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state["messages"] = []
        st.session_state["figures"] = []
        st.rerun()

    # Save / Load session
    st.divider()
    st.subheader("💾 对话持久化")

    save_col, load_col = st.columns(2)
    with save_col:
        if st.button("💾 保存对话", use_container_width=True,
                     help="将当前对话保存到本地文件"):
            from src.utils import save_session_to_file
            path = save_session_to_file()
            st.success(f"已保存到 `{path}`")

    with load_col:
        uploaded_session = st.file_uploader(
            "加载对话",
            type=["json"],
            key="session_loader",
            label_visibility="collapsed",
        )
        if uploaded_session is not None:
            import json
            try:
                backup = json.loads(uploaded_session.read())
                if "messages" in backup:
                    st.session_state["messages"] = backup["messages"]
                    st.session_state["figures"] = []  # figures can't be restored
                    st.success(
                        f"✅ 已恢复 {len(backup['messages'])} 条消息"
                        f"（图表需重新生成）"
                    )
                    st.rerun()
            except Exception as e:
                st.error(f"加载失败: {e}")

    st.divider()

    # Example questions
    st.subheader("💡 示例问题")
    examples = [
        "这个数据集有多少行？有哪些列？",
        "帮我分析一下数据的整体情况",
        "检查哪些列有缺失值",
        "画一张各品类销售额的柱状图",
        "显示数值列之间的相关性热力图",
        "检查价格列是否有异常值",
        "显示销量的分布情况",
        "对比不同地区的平均销售额（箱线图）",
    ]
    for example in examples:
        if st.button(example, key=f"ex_{example[:20]}"):
            st.session_state["_example_clicked"] = example
            st.rerun()

# ── Main Content ─────────────────────────────────────────────────────────
st.title("💬 智能数据对话")
st.caption("用自然语言与你的数据对话，AI 将自动分析并生成可视化图表")

# Display existing chat messages
for i, msg in enumerate(st.session_state.get("messages", [])):
    with st.chat_message(msg["role"]):
        msg_type = msg.get("type", "text")
        if msg_type in ("chart", "chart+text"):
            st.markdown(msg.get("content", ""))
            # Try to re-render saved figures
            figures = st.session_state.get("figures", [])
            fig_idx = msg.get("figure_index", -1)
            if 0 <= fig_idx < len(figures):
                fig_data = figures[fig_idx]
                try:
                    render_figure(fig_data["figure"])
                except Exception:
                    st.caption("(图表已失效，请重新提问)")
        else:
            st.markdown(msg.get("content", ""))

# Chat input
if df is not None:
    # Check for example click
    example_clicked = st.session_state.pop("_example_clicked", None)
    prompt = st.chat_input(
        "输入你的问题，例如：'帮我分析一下销售数据'" if not example_clicked else example_clicked
    )

    if example_clicked:
        prompt = example_clicked

    if prompt:
        # Add user message
        st.session_state["messages"].append({
            "role": "user",
            "content": prompt,
            "type": "text",
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate AI response
        with st.chat_message("assistant"):
            try:
                result = _process_user_message(prompt)

                # Guard against None result (should not happen, but be safe)
                if result is None:
                    result = {
                        "type": "text",
                        "explanation": "⚠️ 处理请求时出错，请重试。",
                    }

                # Render the result
                _handle_llm_result(result, st.empty())

                # Add to message history
                response_type = result.get("type", "text")
                explanation = result.get("explanation", "")

                msg_entry = {
                    "role": "assistant",
                    "content": explanation,
                    "type": response_type,
                }

                if response_type in ("chart", "chart+text") and result.get("code"):
                    figures = st.session_state.get("figures", [])
                    msg_entry["figure_index"] = len(figures) - 1 if figures else -1

                st.session_state["messages"].append(msg_entry)

            except Exception as e:
                error_msg = f"❌ 出错了: {e}"
                st.error(error_msg)
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": error_msg,
                    "type": "text",
                })

else:
    # No data loaded
    st.info("👈 请先在「📊 数据上传」页面上传数据文件，然后回到这里开始对话。")

    # Visual placeholder
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
        ### 🎯 你可以这样问我：
        - "帮我分析一下数据整体情况"
        - "画一张各地区销售额的柱状图"
        - "检查哪些列有异常值"
        - "显示年龄分布的直方图"
        - "数值列之间的相关性如何？"
        """
        )
    with col2:
        st.markdown(
            """
        ### 📊 我能生成的图表：
        - 柱状图 / 折线图 / 散点图
        - 饼图 / 直方图 / 箱线图
        - 热力图 / 面积图 / 小提琴图
        - 旭日图 / 矩形树图 / 漏斗图
        - 以及更多...
        """
        )
