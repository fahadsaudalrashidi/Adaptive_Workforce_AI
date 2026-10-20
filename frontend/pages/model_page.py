"""
Model & AutoML Analytics Page
Displays model comparison, feature importances, and optimal threshold.
BLOCKED for biosignal and unknown dataset types.
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

from frontend.utils.safe_render import guard, safe_error_boundary
from frontend.utils.session_helpers import require_analysis


def render() -> None:
    st.title("Model & AutoML Analytics")
    if not guard("attrition_prediction", "Model Analytics"):
        return
    if not require_analysis():
        return

    ml_res = st.session_state.get("ml_result")
    if ml_res is None:
        st.info("No supervised model was trained (unsupervised mode or no target column).")
        return

    with safe_error_boundary("Model Comparison Table"):
        st.subheader("Model Comparison")
        rows = []
        for name, mr in ml_res.models.items():
            row = {"Model": f"[BEST] {name}" if name == ml_res.best_model_name else name}
            row.update(mr.metrics)
            row["Train (s)"] = mr.train_time_s
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.metric("Optimal Threshold (OOF F1)", f"{ml_res.optimal_threshold:.2f}")

    with safe_error_boundary("Feature Importances Chart"):
        best = ml_res.models.get(ml_res.best_model_name)
        if best and best.feature_importances:
            st.subheader(f"Feature Importances — {ml_res.best_model_name}")
            fi  = best.feature_importances
            top = dict(list(fi.items())[:20])
            fig = px.bar(
                x=list(top.values()), y=list(top.keys()),
                orientation="h",
                title=f"Top {len(top)} Features (raw importances — SHAP integration pending)",
                color=list(top.values()),
                color_continuous_scale="Blues",
            )
            fig.update_layout(showlegend=False, height=500)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Feature importances shown are raw sklearn importances. "
                "SHAP values (more accurate for non-linear models) are planned for a future release."
            )
