from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import streamlit as st

DEBUG_LOG_KEY = "debug_logs"
DEBUG_PLACEHOLDER_KEY = "debug_placeholder"


def clear_debug_logs() -> None:
    st.session_state[DEBUG_LOG_KEY] = []


def set_debug_placeholder(placeholder: Optional["st.delta_generator.DeltaGenerator"]) -> None:
    st.session_state[DEBUG_PLACEHOLDER_KEY] = placeholder


def _render_live_debug_log() -> None:
    placeholder = st.session_state.get(DEBUG_PLACEHOLDER_KEY)
    if not placeholder:
        return
    logs = st.session_state.get(DEBUG_LOG_KEY, [])
    text = "\n".join(logs[-400:]) if logs else "No debug events captured yet."
    placeholder.code(text, language="text")


def debug_log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"[{timestamp}] {message}"
    st.session_state.setdefault(DEBUG_LOG_KEY, []).append(entry)
    print(entry)
    _render_live_debug_log()
