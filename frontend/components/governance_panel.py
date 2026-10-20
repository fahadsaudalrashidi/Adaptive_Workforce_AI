"""
Governance Panel Components
Unified confidence panel and feature trustworthiness panel.
These are the primary AI reliability displays — every executive page should include them.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from backend.core.confidence_governance import (
    UnifiedConfidenceReport,
    EXEC_READY, EXEC_CAUTION, EXEC_LIMITED, EXEC_NOT_READY,
)
from backend.core.calibration_engine import CalibrationReport, CalibrationQuality
from config.settings import HUMAN_OVERSIGHT_DISCLAIMER

_READY_COLORS = {
    EXEC_READY:     ("#16a34a", "#f0fdf4"),
    EXEC_CAUTION:   ("#d97706", "#fffbeb"),
    EXEC_LIMITED:   ("#ea580c", "#fff7ed"),
    EXEC_NOT_READY: ("#dc2626", "#fef2f2"),
}
_BAND_COLORS = {
    "High":       "#16a34a",
    "Moderate":   "#d97706",
    "Low":        "#ea580c",
    "Unreliable": "#dc2626",
    "N/A":        "#6b7280",
}
_TRUST_COLORS = {
    "Reliable":               "#16a34a",
    "Interpret with Caution": "#d97706",
    "High Risk — Validate":   "#dc2626",
}


def render_unified_confidence_panel(
    ucr: Optional[UnifiedConfidenceReport] = None,
) -> None:
    """
    AI Reliability & Governance Summary panel.
    Shows 5-dimension unified confidence with human oversight disclaimer.
    Pass ucr explicitly or reads from session_state.
    """
    if ucr is None:
        ucr = st.session_state.get("unified_confidence")
    if ucr is None:
        st.info("Run analysis to see the AI reliability summary.")
        return

    rc, rbg = _READY_COLORS.get(ucr.executive_readiness, ("#6b7280", "#f9fafb"))
    st.markdown(
        f"""<div style="background:{rbg};border-left:6px solid {rc};
        padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
        <h3 style="color:{rc};margin:0">AI Readiness: {ucr.executive_readiness}</h3>
        <p style="color:{rc};margin:0.5rem 0 0 0">{ucr.executive_reason}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    dims = [ucr.data_quality, ucr.routing_confidence, ucr.model_reliability, ucr.analysis_confidence]
    dim_labels = ["Data Quality", "Routing", "Model Reliability", "Analysis"]
    for col, dim, lbl in zip(cols[:4], dims, dim_labels):
        bc = _BAND_COLORS.get(dim.band, "#6b7280")
        col.markdown(
            f'<div style="text-align:center;padding:8px;border:1px solid {bc};border-radius:6px">'
            f'<div style="font-size:1.3rem;font-weight:700;color:{bc}">{dim.score:.0%}</div>'
            f'<div style="font-size:0.72rem;color:{bc};font-weight:600">{dim.band}</div>'
            f'<div style="font-size:0.7rem;color:#6b7280;margin-top:2px">{lbl}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    lr_color = ("#dc2626" if ucr.leakage_risk_score > 0.3
                else "#d97706" if ucr.leakage_risk_score > 0.1 else "#16a34a")
    lr_label = "High" if ucr.leakage_risk_score > 0.3 else "Low"
    cols[4].markdown(
        f'<div style="text-align:center;padding:8px;border:1px solid {lr_color};border-radius:6px">'
        f'<div style="font-size:1.3rem;font-weight:700;color:{lr_color}">{ucr.leakage_risk_score:.0%}</div>'
        f'<div style="font-size:0.72rem;color:{lr_color};font-weight:600">{lr_label}</div>'
        f'<div style="font-size:0.7rem;color:#6b7280;margin-top:2px">Leakage Risk</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if ucr.caveats:
        with st.expander("Confidence Caveats & Explanations"):
            for caveat in ucr.caveats:
                st.warning(caveat)
            for dim in dims:
                if dim.degraded_by:
                    st.caption(f"**{dim.label}:** {dim.reason}")

    st.markdown(
        f'<div style="background:#fef2f2;border-left:4px solid #dc2626;'
        f'padding:8px 12px;border-radius:4px;font-size:0.82rem;margin-top:8px">'
        f'<strong>Human Oversight Required:</strong> {HUMAN_OVERSIGHT_DISCLAIMER}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_feature_trust_panel(ft=None) -> None:
    """
    Feature Trustworthiness Assessment panel.
    Shows cardinality/dominance warnings with associative (non-causal) language.
    Silent return if no feature trust data — only rendered for HR datasets with model.
    """
    if ft is None:
        ft = st.session_state.get("feature_trust")
    if ft is None:
        return

    tc = _TRUST_COLORS.get(ft.overall_trust, "#6b7280")
    st.markdown(
        f'<div style="background:{tc}15;border-left:5px solid {tc};'
        f'padding:0.8rem 1.2rem;border-radius:6px;margin-bottom:1rem">'
        f'<strong style="color:{tc}">Feature Trust: {ft.overall_trust}</strong><br>'
        f'<span style="color:#374151">{ft.summary}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if ft.has_dominance_warning or ft.has_cardinality_risk:
        st.warning(
            "Some features require careful interpretation. "
            "Associations shown are statistical patterns, not causal relationships."
        )
    if ft.downgrade_model_reliability and ft.downgrade_reason:
        st.error(f"Model reliability may be overstated: {ft.downgrade_reason}")

    if ft.assessments:
        rows = [{
            "Feature":          a.feature_name,
            "Importance":       f"{a.importance_share:.0%}",
            "Type":             a.dtype.title(),
            "Unique Values":    a.n_unique,
            "Cardinality Risk": a.cardinality_risk,
            "Dominance":        a.dominance_risk,
            "Trust Level":      a.trust_level,
        } for a in ft.assessments[:15]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        top = ft.assessments[0]
        st.info(f"**Top predictor '{top.feature_name}':** {top.associative_note}")

    if ft.recommendations:
        with st.expander("Feature Recommendations"):
            for rec in ft.recommendations:
                st.write(f"- {rec}")


_CALIB_COLORS = {
    CalibrationQuality.GOOD:          ("#16a34a", "#f0fdf4"),
    CalibrationQuality.MODERATE:      ("#d97706", "#fffbeb"),
    CalibrationQuality.POOR:          ("#dc2626", "#fef2f2"),
    CalibrationQuality.NOT_EVALUATED: ("#6b7280", "#f9fafb"),
}


def render_calibration_panel(cal: Optional[CalibrationReport] = None) -> None:
    """
    Model Calibration Quality panel.
    Shows Brier score, ECE, overconfidence/underconfidence warnings,
    and a reliability summary. Silent return if no calibration data available.
    """
    if cal is None:
        cal = st.session_state.get("calibration_report")
    if cal is None:
        return

    cc, cbg = _CALIB_COLORS.get(cal.quality, ("#6b7280", "#f9fafb"))
    quality_label = cal.quality.value if hasattr(cal.quality, "value") else str(cal.quality)

    st.markdown(
        f'<div style="background:{cbg};border-left:5px solid {cc};'
        f'padding:0.8rem 1.2rem;border-radius:6px;margin-bottom:0.5rem">'
        f'<strong style="color:{cc}">Model Calibration: {quality_label}</strong><br>'
        f'<span style="color:#374151;font-size:0.85rem">{cal.summary}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    brier_str = f"{cal.brier_score:.4f}" if cal.brier_score is not None else "N/A"
    ece_str   = f"{cal.ece:.4f}"         if cal.ece is not None         else "N/A"
    n_str     = str(cal.n_samples)       if cal.n_samples is not None   else "N/A"

    col1.metric("Brier Score", brier_str, help="0 = perfect, 0.25 = random baseline")
    col2.metric("Calibration ECE", ece_str, help="Expected Calibration Error — lower is better")
    col3.metric("Calibration Samples", n_str)

    if cal.overconfident:
        st.warning(
            "Overconfidence detected: the model predicts higher probabilities than the actual "
            "outcome rate. Risk scores may be systematically overstated — apply additional "
            "human judgement before acting on high-risk flags."
        )
    if cal.underconfident:
        st.info(
            "Underconfidence detected: the model's predicted probabilities are lower than the "
            "actual outcome rate. Some at-risk individuals may be scored lower than warranted."
        )

    if cal.caveats:
        with st.expander("Calibration Caveats"):
            for caveat in cal.caveats:
                st.caption(caveat)
