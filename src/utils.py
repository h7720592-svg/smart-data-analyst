"""Shared utilities: session state, logging, configuration."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st


def setup_logging(level: str = "INFO") -> None:
    """Configure Python logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def init_session_state() -> None:
    """Initialize all Streamlit session state keys with defaults.

    Must be called at the top of every page to ensure state exists.
    """
    defaults = {
        # Data
        "df": None,
        "df_metadata": None,
        "df_schema": None,
        "df_summary": None,
        "df_issues": None,
        "profile_report_path": None,
        # LLM
        "llm_provider": "deepseek",
        "llm_model": "deepseek-v4-flash",
        "llm_api_key": "",
        "llm_base_url": "",
        "llm_thinking": False,
        # Chat
        "messages": [],
        "figures": [],
        # Config
        "language": "zh",
        "initialized": False,
    }

    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    st.session_state["initialized"] = True


def load_env_file() -> dict[str, str]:
    """Load environment variables from .env file.

    Returns:
        dict of loaded environment variables.
    """
    env_vars = {}
    env_path = Path(".env")
    if not env_path.exists():
        return env_vars

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    env_vars[key] = value
    except Exception:
        pass

    return env_vars


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider from session state or environment.

    Priority: session state > environment variable > .env file.

    Args:
        provider: LLM provider name (deepseek, openai, groq).

    Returns:
        API key string or None.
    """
    # Check session state — provider-specific key first, then generic key
    state_key = f"llm_api_key_{provider}"
    if state_key in st.session_state and st.session_state[state_key]:
        return st.session_state[state_key]
    if "llm_api_key" in st.session_state and st.session_state["llm_api_key"]:
        return st.session_state["llm_api_key"]

    # Check st.secrets (Streamlit Cloud)
    try:
        env_key = f"{provider.upper()}_API_KEY"
        if env_key in st.secrets:
            return st.secrets[env_key]
    except Exception:
        pass

    # Check environment variables
    env_key = f"{provider.upper()}_API_KEY"
    key = os.environ.get(env_key)
    if key:
        return key

    # Check .env file
    env_vars = load_env_file()
    return env_vars.get(env_key)


def format_number(n: int) -> str:
    """Format large numbers with commas (Chinese style: 万, 亿 for display)."""
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}亿"
    elif n >= 10_000:
        return f"{n / 10_000:.1f}万"
    else:
        return f"{n:,}"


def get_llm_config() -> dict:
    """Build LLM configuration from session state.

    Returns:
        dict with provider, model, api_key, base_url.
    """
    provider = st.session_state.get("llm_provider", "deepseek")
    model = st.session_state.get("llm_model", "deepseek-v4-flash")

    api_key = (
        st.session_state.get("llm_api_key", "")
        or get_api_key(provider)
        or ""
    )

    base_url = st.session_state.get("llm_base_url", "")
    if not base_url:
        # Default base URLs
        defaults = {
            "deepseek": "https://api.deepseek.com/v1",
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "ollama": "http://localhost:11434/v1",
        }
        base_url = defaults.get(provider, "")

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
    }


def save_session_to_file(filepath: str = "session_backup.json") -> str:
    """Save current conversation state to a JSON file.

    Saves messages and figures metadata (not the Plotly figure objects).

    Args:
        filepath: Path to save the session backup.

    Returns:
        The filepath where data was saved.
    """
    messages = st.session_state.get("messages", [])
    figures_meta = []
    for f in st.session_state.get("figures", []):
        figures_meta.append({
            "explanation": f.get("explanation", ""),
            # Plotly figures can't be serialized, skip figure data
        })

    # Collect metadata about the dataset
    metadata = st.session_state.get("df_metadata", {})
    data_info = {
        "filename": metadata.get("filename", ""),
        "rows": metadata.get("rows", 0),
        "columns": metadata.get("columns", 0),
        "file_type": metadata.get("file_type", ""),
    } if metadata else {}

    backup = {
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_info": data_info,
        "message_count": len(messages),
        "figure_count": len(figures_meta),
        "messages": messages,
        "figures_meta": figures_meta,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)

    return filepath


def load_session_from_file(filepath: str = "session_backup.json") -> dict | None:
    """Load a previously saved conversation session.

    Args:
        filepath: Path to the session backup file.

    Returns:
        dict with messages and metadata, or None if file doesn't exist.
    """
    path = Path(filepath)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            backup = json.load(f)
        return backup
    except (json.JSONDecodeError, OSError):
        return None
