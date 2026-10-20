"""
Formatting Utilities
Currency formatting, confidence badges, HTML helpers.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import DEFAULT_CURRENCY, CURRENCY_SYMBOLS, CURRENCY_OPTIONS

import streamlit as st


def get_currency() -> str:
    """Get the configured currency from session state."""
    return st.session_state.get("currency", DEFAULT_CURRENCY)


def get_currency_symbol() -> str:
    """Get the symbol/prefix for the configured currency."""
    curr = get_currency()
    return CURRENCY_SYMBOLS.get(curr, curr)


def fmt_currency(amount: float, currency: Optional[str] = None) -> str:
    """Format a monetary value with the configured currency symbol."""
    curr = currency or get_currency()
    sym = CURRENCY_SYMBOLS.get(curr, curr)
    return f"{sym} {amount:,.0f}"


def fmt_pct(v: float, dp: int = 1) -> str:
    """Format a fraction as percentage string."""
    return f"{v:.{dp}%}"


def fmt_score(v: float) -> str:
    """Format a 0-100 score."""
    return f"{v:.0f}/100"


def confidence_badge_html(band: str, score: float) -> str:
    """Return inline HTML for a confidence band badge."""
    colors = {
        "High":       ("#16a34a", "#f0fdf4"),
        "Moderate":   ("#d97706", "#fffbeb"),
        "Low":        ("#ea580c", "#fff7ed"),
        "Unreliable": ("#dc2626", "#fef2f2"),
        "N/A":        ("#6b7280", "#f9fafb"),
    }
    c, bg = colors.get(band, ("#6b7280", "#f9fafb"))
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c};'
        f'border-radius:4px;padding:2px 8px;font-size:0.82rem;font-weight:700">'
        f'{band} {score:.0%}</span>'
    )


def readiness_badge_html(readiness: str) -> str:
    """Return inline HTML for an executive readiness badge."""
    colors = {
        "Ready":     ("#16a34a", "#f0fdf4"),
        "Caution":   ("#d97706", "#fffbeb"),
        "Limited":   ("#ea580c", "#fff7ed"),
        "Not Ready": ("#dc2626", "#fef2f2"),
    }
    c, bg = colors.get(readiness, ("#6b7280", "#f9fafb"))
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c};'
        f'border-radius:4px;padding:3px 10px;font-size:0.85rem;font-weight:700">'
        f'{readiness}</span>'
    )
