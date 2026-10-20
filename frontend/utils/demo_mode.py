"""
Company Demo Mode Utilities
Controls which pages and panels are visible in demo mode.
"""
from __future__ import annotations

import streamlit as st

# Pages visible in Company Demo Mode (executive-safe only)
DEMO_PAGES = [
    "Adaptive Dataset Intelligence",
    "HR Attrition Analytics",
    "Department & Org Risk",
    "Executive Insights & Actions",
    "Explainability & Governance",
    "Data Quality Report",
]

# All available pages
ALL_PAGES = [
    "Adaptive Dataset Intelligence",
    "HR Attrition Analytics",
    "Psychological Risk Intelligence",
    "Biosignal Intelligence",
    "Time-Series Early Warning",
    "Department & Org Risk",
    "Executive Insights & Actions",
    "Model & AutoML Analytics",
    "Explainability & Governance",
    "Data Quality Report",
]


def is_demo_mode() -> bool:
    return bool(st.session_state.get("demo_mode", False))


def get_visible_pages() -> list:
    return DEMO_PAGES if is_demo_mode() else ALL_PAGES


def should_mask_ids() -> bool:
    return bool(st.session_state.get("mask_employee_ids", True))


def mask_employee_id(idx: any, position: int) -> str:
    """Return masked or raw employee identifier based on demo/mask settings."""
    if should_mask_ids():
        return f"Employee #{position + 1:03d}"
    return str(idx)
