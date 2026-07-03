"""Smart Data Analyst — AI-powered data analysis and visualization.

Entry point for the Streamlit application.
"""

import logging
from pathlib import Path

import streamlit as st

from src.utils import init_session_state, setup_logging

# ── App Configuration ────────────────────────────────────────────────────
st.set_page_config(
    page_title="智能数据分析助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/h7720592-svg/smart-data-analyst/issues",
        "Report a bug": "https://github.com/h7720592-svg/smart-data-analyst/issues/new",
        "About": (
            "# 智能数据分析助手\n"
            "AI-powered data analysis and visualization.\n\n"
            "上传数据 → AI 自动分析 → 生成可视化 → 导出报告\n\n"
            "开源项目，MIT License"
        ),
    },
)

# ── Setup ─────────────────────────────────────────────────────────────────
setup_logging(level="INFO")
logger = logging.getLogger(__name__)

# Load custom CSS
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize session state (must be called on all pages too)
init_session_state()

# ── Navigation ───────────────────────────────────────────────────────────
# Streamlit automatically handles multi-page navigation via the pages/ directory.
# This file serves as the main entry point.

pg = st.navigation(
    [
        st.Page("pages/01_📊_数据上传.py", title="数据上传", icon="📊"),
        st.Page("pages/02_💬_智能对话.py", title="智能对话", icon="💬"),
        st.Page("pages/03_📄_导出报告.py", title="导出报告", icon="📄"),
    ],
    position="sidebar",
)

# ── Run ───────────────────────────────────────────────────────────────────
pg.run()
