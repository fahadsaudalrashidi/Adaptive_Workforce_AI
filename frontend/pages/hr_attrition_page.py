"""
HR Attrition Analytics Page
Displays workforce risk metrics, attrition distribution, and governance panels.
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
from frontend.utils.safe_render import (
    guard, require_analysis,
    render_employee_metrics, render_attrition, render_retention_roi,
)
from frontend.components.governance_panel import (
    render_unified_confidence_panel, render_feature_trust_panel, render_calibration_panel,
)
from frontend.utils.safe_render import safe_error_boundary


def render() -> None:
    st.title("HR Attrition Analytics")
    if not guard("attrition_prediction", "HR Attrition Analytics"):
        return
    if not require_analysis():
        return

    contract  = st.session_state.get("contract")
    org_risk  = st.session_state.get("org_risk")
    ind_risks = st.session_state.get("ind_risks") or []
    ml_res    = st.session_state.get("ml_result")

    if org_risk is None:
        st.warning("No risk data available — re-run analysis.")
        return

    _curr     = st.session_state.get("currency", DEFAULT_CURRENCY)
    _curr_sym = CURRENCY_SYMBOLS.get(_curr, _curr)
    row_lbl   = contract.row_label().title() if contract else "Employee"

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Total {row_lbl}", f"{org_risk.total_employees:,}")
    c2.metric("Overall Attrition Risk", f"{org_risk.overall_attrition_risk:.1%}")
    c3.metric(f"High-Risk {row_lbl}", f"{org_risk.high_risk_employees:,}")
    c4.metric("Early Warning", org_risk.early_warning_level)

    c5, c6 = st.columns(2)
    c5.metric(f"Estimated Exposure ({_curr_sym})", f"{_curr_sym} {org_risk.total_financial_exposure:,.0f}")
    c6.metric("Sustainability Score", f"{org_risk.sustainability_score:.0f}/100")

    st.divider()
    with safe_error_boundary("AI Reliability & Governance"):
        render_unified_confidence_panel()
    with safe_error_boundary("Model Calibration"):
        render_calibration_panel()
    with safe_error_boundary("Feature Trustworthiness"):
        render_feature_trust_panel()
    st.divider()

    # Attrition distribution
    def _attrition_dist():
        if not ind_risks:
            return
        probs  = [r.attrition_probability for r in ind_risks]
        thresh = ml_res.optimal_threshold if ml_res else 0.50
        fig = px.histogram(
            x=probs, nbins=30,
            title="Attrition Probability Distribution",
            labels={"x": "Attrition Probability"},
            color_discrete_sequence=["#3b82f6"],
        )
        fig.add_vline(x=thresh, line_dash="dash", line_color="red",
                      annotation_text=f"Threshold {thresh:.2f}")
        st.plotly_chart(fig, use_container_width=True)

    with safe_error_boundary("Attrition Distribution Chart"):
        render_attrition(_attrition_dist)

    # Model performance table
    if ml_res and ml_res.models:
        st.subheader("Model Performance")
        with safe_error_boundary("Model Performance Table"):
            rows = []
            for name, mr in ml_res.models.items():
                row = {"Model": f"Best: {name}" if name == ml_res.best_model_name else name}
                row.update(mr.metrics)
                row["Train (s)"] = mr.train_time_s
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Top risk table
    def _top_risk_table():
        if not ind_risks:
            return
        st.subheader(f"Top 20 Highest-Risk {row_lbl} — Flagged for HR Review")
        st.caption(
            "Identifiers are masked by default. "
            "This list is for HR review purposes only — no automated action should be taken."
        )
        _mask   = st.session_state.get("mask_employee_ids", True)
        sorted_r = sorted(ind_risks, key=lambda r: r.attrition_probability, reverse=True)[:20]
        tbl = pd.DataFrame([{
            "ID":                f"{row_lbl} #{i+1:03d}" if _mask else str(r.employee_idx),
            "Predicted Risk":    f"{r.attrition_probability:.1%}",
            "Risk Level":        r.risk_level,
            "Burnout Indicator": "N/A" if r.burnout_risk is None else f"{r.burnout_risk:.1%}",
            "Burnout Source":    getattr(r, "burnout_mode", "—"),
            f"Exposure ({_curr_sym})": f"{_curr_sym} {r.financial_exposure:,.0f}",
            "Review Status": (
                "Flagged for HR review"
                if r.risk_level in ("High", "Critical")
                else "Standard monitoring"
            ),
        } for i, r in enumerate(sorted_r)])
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    with safe_error_boundary("Top Risk Table"):
        render_employee_metrics(_top_risk_table)

    # Retention ROI
    def _retention_roi():
        st.subheader("Retention ROI Summary")
        c1, c2 = st.columns(2)
        c1.metric(f"Estimated Exposure ({_curr_sym})", f"{_curr_sym} {org_risk.total_financial_exposure:,.0f}")
        c2.metric("High-Risk Headcount", org_risk.high_risk_employees)
        st.caption(
            f"Replacement cost estimated at ~50% annual salary per attriting employee. "
            f"Currency: {_curr}."
        )

    with safe_error_boundary("Retention ROI"):
        render_retention_roi(_retention_roi)
