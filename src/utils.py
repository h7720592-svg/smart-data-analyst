"""Shared utilities: session state, logging, configuration."""

import logging
import os
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
