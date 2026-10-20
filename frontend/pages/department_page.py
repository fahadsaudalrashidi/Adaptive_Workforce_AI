"""
Department & Organisational Risk Page
Real department detection — shows honest unavailable message if no dept column.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from config.settings import DEFAULT_CURRENCY, CURRENCY_SYMBOLS
from frontend.utils.safe_render import guard, require_analysis, render_department


def render() -> None:
    st.title("Department & Organisational Risk")
    if not guard("department_stability", "Department & Org Risk"):
        return
    if not require_analysis():
        return

    contract   = st.session_state.get("contract")
    org_risk   = st.session_state.get("org_risk")
    dept_risks = st.session_state.get("dept_risks") or []

    _curr     = st.session_state.get("currency", DEFAULT_CURRENCY)
    _curr_sym = CURRENCY_SYMBOLS.get(_curr, _curr)
    row_lbl   = contract.row_label().title() if contract else "Employee"

    # Org KPIs always shown
    if org_risk:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Total {row_lbl}", f"{org_risk.total_employees:,}")
        c2.metric("High-Risk",        f"{org_risk.high_risk_employees:,}")
        c3.metric("Sustainability",   f"{org_risk.sustainability_score:.0f}/100")
        c4.metric("Early Warning",    org_risk.early_warning_level)
        st.divider()

    # Department breakdown — honest if unavailable
    dept_col_found = getattr(org_risk, "department_column_found", None) if org_risk else None
    if dept_col_found is False:
        st.info(
            "**Department-level analysis unavailable** — no department column was detected "
            "in this dataset.  \nTo enable department breakdowns, ensure your dataset includes "
            "a column named 'Department', 'Division', 'Business Unit', 'Team', or similar."
        )
        return

    def _dept_render():
        if not dept_risks:
            st.info(
                "Department breakdown could not be computed. "
                "This may occur if fewer than 5 employees share the same department label."
            )
            return

        dept_df = pd.DataFrame([{
            "Department":              d.department,
            "Headcount":               d.n_employees,
            "Avg Risk":                d.avg_attrition_prob,
            "High Risk %":             d.high_risk_pct,
            f"Exposure ({_curr_sym})": f"{_curr_sym} {d.total_financial_exposure:,.0f}",
            "Reliability":             d.reliability_flag,
        } for d in dept_risks])

        fig = px.bar(
            dept_df, x="Department", y="Avg Risk",
            color="Avg Risk", color_continuous_scale="RdYlGn_r",
            title="Average Attrition Risk by Department — For HR Review",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dept_df, use_container_width=True, hide_index=True)
        st.caption(
            "Small departments (< 5 records) are marked unreliable. "
            "These figures are statistical associations, not causal findings."
        )

    render_department(_dept_render)
