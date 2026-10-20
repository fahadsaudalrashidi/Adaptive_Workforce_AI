"""
Psychological Risk Intelligence Page
Displays estimated psychological construct scores.
BLOCKED for biosignal and unknown dataset types.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from frontend.utils.safe_render import guard, safe_error_boundary
from frontend.utils.session_helpers import require_analysis

_CONSTRUCTS = [
    "BurnoutRiskComposite", "SatisfactionIndex", "EngagementScore",
    "RetentionRisk", "ManagerialSupportIndex", "EmployeeStabilityRisk",
    "CompensationEquity", "WorkLifeBalanceRisk", "CareerProgressionScore",
    "PsychologicalWellbeingScore",
]


def render() -> None:
    st.title("Psychological Risk Intelligence")
    if not guard("psychological_constructs", "Psychological Risk Intelligence"):
        return
    if not require_analysis():
        return

    df_eng = st.session_state.get("df_eng")
    if df_eng is None:
        st.warning("No data available.")
        return

    constructs = [c for c in _CONSTRUCTS if c in df_eng.columns]

    if not constructs:
        st.info(
            "No psychological constructs were estimated for this dataset.  \n"
            "Constructs require relevant HR columns such as satisfaction scores, "
            "overtime hours, work-life balance ratings, and performance data."
        )
        return

    st.caption(
        f"**{len(constructs)} construct(s) estimated** from available HR features.  \n"
        "All scores are statistical associations — not clinical assessments. "
        "Human HR expertise is required for any individual interpretation."
    )

    with safe_error_boundary("Construct Bar Chart"):
        means = {c: float(df_eng[c].mean()) for c in constructs}
        fig = go.Figure(go.Bar(
            x=list(means.values()), y=list(means.keys()),
            orientation="h",
            marker_color=["#dc2626" if v > 0.65 else "#3b82f6" for v in means.values()],
            text=[f"{v:.3f}" for v in means.values()],
            textposition="outside",
        ))
        fig.update_layout(
            title="Mean Construct Scores (0-1 scale)",
            xaxis_title="Score",
            xaxis=dict(range=[0, 1]),
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)

    if len(constructs) >= 3:
        with safe_error_boundary("Construct Correlation Matrix"):
            corr = df_eng[constructs].corr()
            fig2 = px.imshow(
                corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                title="Construct Correlation Matrix",
                zmin=-1, zmax=1,
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.warning(
        "Psychological constructs are derived from HR data patterns, not clinical instruments. "
        "They indicate associations and should not be used for individual employment decisions "
        "without qualified HR professional review."
    )
