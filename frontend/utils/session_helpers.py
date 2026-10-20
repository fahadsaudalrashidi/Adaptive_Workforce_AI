"""
Session State Helpers — Single source of truth for session_state accessors.

All page modules must use these helpers instead of defining local copies.
This prevents drift between _contract(), _require_analysis(), and other
session accessors as the platform evolves.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from backend.core.dataset_contract import DatasetContract


def get_contract() -> Optional[DatasetContract]:
    """Return the current DatasetContract from session state, or None."""
    return st.session_state.get("contract")


def require_analysis(page_key: str = "") -> bool:
    """
    Guard that returns True only if analysis has been run.
    Shows an info message and returns False otherwise.
    """
    if not st.session_state.get("analysis_done"):
        st.info("Run analysis from the **Adaptive Dataset Intelligence** page first.")
        return False
    return True


def get_currency() -> str:
    """Return the configured currency code (default: SAR)."""
    from config.settings import DEFAULT_CURRENCY
    return st.session_state.get("currency", DEFAULT_CURRENCY)


def get_currency_symbol() -> str:
    """Return the configured currency symbol."""
    from config.settings import CURRENCY_SYMBOLS, DEFAULT_CURRENCY
    _curr = st.session_state.get("currency", DEFAULT_CURRENCY)
    return CURRENCY_SYMBOLS.get(_curr, _curr)


def get_mask_ids() -> bool:
    """Return whether employee IDs should be masked."""
    return st.session_state.get("mask_employee_ids", True)
