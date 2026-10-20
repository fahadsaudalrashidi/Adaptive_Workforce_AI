"""
Safe Employee Tables
Employee-level risk tables with ID masking, safe language, and currency formatting.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from config.settings import DEFAULT_CURRENCY, CURRENCY_SYMBOLS


def top_risk_table(
    ind_risks: list,
    n: int = 20,
    currency: Optional[str] = None,
    mask_ids: bool = True,
    row_label: str = "employee",
) -> None:
    """
    Render top-N highest-risk records with safe language and ID masking.
    Burnout shown as N/A when evidence unavailable (never fake 0%).
    """
    if not ind_risks:
        return

    curr = currency or st.session_state.get("currency", DEFAULT_CURRENCY)
    curr_sym = CURRENCY_SYMBOLS.get(curr, curr)

    sorted_r = sorted(ind_risks, key=lambda r: r.attrition_probability, reverse=True)[:n]

    st.caption(
        f"Top {len(sorted_r)} {row_label}s flagged for HR review — identifiers are "
        f"{'masked' if mask_ids else 'unmasked'}. "
        "This list is for HR review purposes only. No automated action should be taken."
    )

    rows = [{
        "ID":                 f"{row_label.title()} #{i+1:03d}" if mask_ids else str(r.employee_idx),
        "Predicted Risk":     f"{r.attrition_probability:.1%}",
        "Risk Level":         r.risk_level,
        "Burnout Indicator":  "N/A" if r.burnout_risk is None else f"{r.burnout_risk:.1%}",
        "Burnout Source":     getattr(r, "burnout_mode", "—"),
        f"Exposure ({curr_sym})": f"{curr_sym} {r.financial_exposure:,.0f}",
        "Review Status": (
            "Flagged for HR review"
            if r.risk_level in ("High", "Critical")
            else "Standard monitoring"
        ),
    } for i, r in enumerate(sorted_r)]

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
