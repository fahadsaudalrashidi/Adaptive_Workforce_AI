"""
Executive Insights & Action Plan Page
Decision-support insights with safe HR language and human oversight disclaimer.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from config.settings import HUMAN_OVERSIGHT_DISCLAIMER
from frontend.utils.safe_render import require_analysis


def render() -> None:
    st.title("Executive Insights & Action Plan")
    if not require_analysis():
        return

    insight_rep = st.session_state.get("insight_report")
    contract    = st.session_state.get("contract")

    if insight_rep is None:
        st.warning("No insight report available.")
        return

    # Human oversight disclaimer — always shown first
    st.markdown(
        f"""<div style="background:#fefce8;border-left:4px solid #ca8a04;
        padding:0.75rem 1rem;border-radius:6px;margin-bottom:0.75rem;font-size:0.88rem">
        <b style="color:#92400e">Human Oversight Required</b><br>
        <span style="color:#78350f">{HUMAN_OVERSIGHT_DISCLAIMER}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    if contract and contract.is_biosignal:
        st.info(
            "Biosignal mode — physiological signal insights shown.  \n"
            "No employee metrics, attrition probabilities, or workforce analytics."
        )

    st.info(insight_rep.executive_summary)

    colors = {
        "Critical": "#dc2626", "Elevated": "#ea580c",
        "Watchlist": "#d97706", "Stable":   "#16a34a",
    }
    lv  = insight_rep.risk_headline
    col = colors.get(lv, "#374151")
    st.markdown(
        f"""<div style="background:{col}22;border-left:5px solid {col};
        padding:0.8rem 1rem;border-radius:6px">
        <b style="color:{col}">Risk Signal: {lv}</b>
        <span style="color:#6b7280;font-size:0.82rem"> — Statistical indicator only.
        Human validation required before any action.</span></div>""",
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("Key Decision-Support Insights")
    for ins in insight_rep.insights:
        icon = {
            "risk":           "🔴",
            "warning":        "🟡",
            "opportunity":    "🟢",
            "recommendation": "🔵",
        }.get(ins.category, "⚪")
        with st.expander(f"{icon} [{ins.category.upper()}] {ins.title}"):
            st.write(ins.body)
            if ins.action:
                st.success(f"**Suggested HR Action (requires validation):** {ins.action}")

    # 30/60/90 day plan — only for non-biosignal
    if not (contract and contract.is_biosignal):
        st.divider()
        st.subheader("30 / 60 / 90-Day Action Plan")
        c30, c60, c90 = st.columns(3)
        with c30:
            st.markdown("**30-Day**")
            for a in insight_rep.recommended_actions_30d or ["None identified"]:
                st.markdown(f"- {a}")
        with c60:
            st.markdown("**60-Day**")
            for a in insight_rep.recommended_actions_60d or ["None identified"]:
                st.markdown(f"- {a}")
        with c90:
            st.markdown("**90-Day**")
            for a in insight_rep.recommended_actions_90d or ["None identified"]:
                st.markdown(f"- {a}")
