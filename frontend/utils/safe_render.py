"""
Safe-Render Utilities
Each wrapper blocks inappropriate rendering based on DatasetContract.
Biosignal datasets NEVER show employee metrics, attrition probs, or HR charts.
"""
from __future__ import annotations

import sys
import logging
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Any, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd

from backend.core.dataset_contract import DatasetContract

logger = logging.getLogger(__name__)


def _get_contract() -> Optional[DatasetContract]:
    return st.session_state.get("contract")


# ─────────────────────────────────────────────────────────────────────────────
# CONTRACT GUARD
# ─────────────────────────────────────────────────────────────────────────────

def guard(analysis_key: str, page_name: str) -> bool:
    """
    Returns True if the analysis is allowed by the contract.
    Shows a styled block message and returns False if blocked.
    Call this as the FIRST statement in every page function.
    """
    c = _get_contract()
    if c is None:
        st.info("Upload a dataset from the sidebar, then run analysis.")
        return False
    if c.blocks(analysis_key):
        reason = next(
            (e.reason for e in c.compatibility_matrix if e.analysis_key == analysis_key),
            "Not applicable for this dataset type",
        )
        st.error(
            f"**{page_name}** is not available for this dataset.\n\n"
            f"**Dataset type**: {c.dataset_type.replace('_', ' ').title()}  \n"
            f"**Row unit**: {c.row_label()}  \n"
            f"**Reason**: {reason}"
        )
        if c.is_biosignal:
            st.info(
                "This file contains physiological signal data (NOT employee records). "
                "Navigate to **Biosignal Intelligence** for the appropriate analysis."
            )
        return False
    return True


def require_analysis(page_key: str = "") -> bool:
    if not st.session_state.get("analysis_done"):
        st.info("Run analysis from the **Adaptive Dataset Intelligence** page first.")
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# RENDER GUARDS
# ─────────────────────────────────────────────────────────────────────────────

def render_employee_metrics(render_fn: Callable[[], Any]) -> None:
    """Execute render_fn ONLY if dataset has employee-level rows."""
    c = _get_contract()
    if c is None:
        return
    if c.is_biosignal or c.row_unit == "signal_samples":
        st.warning(
            f"Employee metrics are not applicable for "
            f"**{c.dataset_type.replace('_',' ').title()}** datasets.  \n"
            f"Rows in this file represent **{c.row_label()}**, not employees."
        )
        return
    render_fn()


def render_attrition(render_fn: Callable[[], Any]) -> None:
    """Execute render_fn ONLY if attrition_prediction is allowed."""
    c = _get_contract()
    if c is None:
        return
    if c.blocks("attrition_prediction"):
        reason = next(
            (e.reason for e in c.compatibility_matrix
             if e.analysis_key == "attrition_prediction"),
            "Attrition prediction not applicable",
        )
        st.warning(f"Attrition analysis blocked — {reason}")
        return
    render_fn()


def render_department(render_fn: Callable[[], Any]) -> None:
    """Execute render_fn ONLY if department_stability is allowed."""
    c = _get_contract()
    if c is None:
        return
    if c.blocks("department_stability"):
        reason = next(
            (e.reason for e in c.compatibility_matrix
             if e.analysis_key == "department_stability"),
            "Department analysis not applicable",
        )
        st.warning(f"Department analysis blocked — {reason}")
        return
    render_fn()


def render_retention_roi(render_fn: Callable[[], Any]) -> None:
    """Execute render_fn ONLY if retention_roi is allowed."""
    c = _get_contract()
    if c is None:
        return
    if c.blocks("retention_roi"):
        if c and c.is_biosignal:
            st.warning(
                "Replacement cost / retention ROI requires employee salary data. "
                "This is a physiological signal dataset — no salary data present."
            )
        else:
            st.warning("Retention ROI requires salary + attrition data.")
        return
    render_fn()


@contextmanager
def safe_error_boundary(section_name: str = "display section", show_warning: bool = True):
    """
    Context manager for every advanced rendering block in the UI.

    Catches ALL exceptions at the UI boundary:
    - Logs full traceback internally (never to UI)
    - Shows a governance-safe warning instead of raw exception
    - Preserves session state on failure
    - NEVER exposes: traceback, stack trace, raw exception, internal paths

    Usage:
        with safe_error_boundary("Attrition Chart"):
            st.plotly_chart(fig)
    """
    try:
        yield
    except Exception as exc:
        logger.error(
            "safe_error_boundary caught exception in [%s]: %s\n%s",
            section_name,
            exc,
            traceback.format_exc(),
        )
        if show_warning:
            st.warning(
                f"**{section_name}** could not be displayed due to a rendering issue.  \n"
                "Your analysis data is intact. Please contact your system administrator if this persists."
            )


def safe_dataframe(df: pd.DataFrame, styler_func=None, **kwargs) -> None:
    """Render DataFrame with optional styling; falls back gracefully if jinja2 missing."""
    if styler_func is not None:
        try:
            st.dataframe(df.style.apply(styler_func, axis=1), **kwargs)
            return
        except Exception as exc:
            msg = str(exc).lower()
            if "jinja2" in msg or "style" in msg or "styler" in msg:
                st.dataframe(df, **kwargs)
                st.caption("Row colouring disabled — install jinja2 to enable.")
                return
            raise
    st.dataframe(df, **kwargs)
