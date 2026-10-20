"""
Time-Series Early Warning Page
Trend analysis, forecasts, and anomaly detection over time cohorts.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from frontend.utils.safe_render import guard, safe_error_boundary
from frontend.utils.session_helpers import require_analysis


def render() -> None:
    st.title("Time-Series Early Warning")
    if not guard("timeseries_forecast", "Time-Series Early Warning"):
        return
    if not require_analysis():
        return

    ts_res = st.session_state.get("ts_result")
    if ts_res is None or ts_res.n_periods == 0:
        st.warning("No time-series data available for this dataset.")
        return

    if ts_res.synthetic_mode:
        st.info("Synthetic tenure-cohort timeline (no date column detected).")

    with safe_error_boundary("Early Warning Escalation"):
        esc = ts_res.escalation
        if esc:
            esc_colors = {
                "Critical":  "#dc2626",
                "Elevated":  "#ea580c",
                "Watchlist": "#d97706",
                "Stable":    "#16a34a",
            }
            col = esc_colors.get(esc.level, "#374151")
            st.markdown(
                f"""<div style="background:{col}22;border-left:6px solid {col};
                padding:1rem;border-radius:8px">
                <h3 style="color:{col}">Early Warning: {esc.level} (Score: {esc.score:.0f}/100)</h3>
                <p>{esc.recommended_action}</p>
                {"".join(f"<p>- {d}</p>" for d in esc.drivers)}
                </div>""",
                unsafe_allow_html=True,
            )

    with safe_error_boundary("Trend Analysis"):
        for metric, trend in ts_res.trends.items():
            st.subheader(f"Trend: {metric}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Direction", trend.direction.title())
            c2.metric("Magnitude", trend.magnitude.title())
            c3.metric("R²",    f"{trend.r_squared:.3f}")
            c4.metric("p-value",    f"{trend.p_value:.3f}")

    with safe_error_boundary("Forecast Table"):
        if ts_res.forecasts:
            st.subheader("Forecast with 95% Confidence Bands")
            rows = [{
                "Horizon":    h,
                "Projected":  f"{fc.projected:.4f}",
                "Lower 95%":  f"{fc.lower_95:.4f}",
                "Upper 95%":  f"{fc.upper_95:.4f}",
                "CI Width":   f"{fc.band_width:.4f}",
                "Confidence": f"{fc.confidence:.0%}",
                "Method":     fc.method,
            } for h, fc in ts_res.forecasts.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with safe_error_boundary("Anomaly Table"):
        if ts_res.anomalies:
            st.subheader(f"Anomalies ({len(ts_res.anomalies)})")
            adf = pd.DataFrame([{
                "Period":   a.period,
                "Metric":   a.metric,
                "Value":    a.value,
                "Z-Score":  a.z_score,
                "Severity": a.severity,
            } for a in ts_res.anomalies])
            st.dataframe(adf, use_container_width=True, hide_index=True)
