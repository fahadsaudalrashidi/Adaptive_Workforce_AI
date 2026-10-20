"""
Data Quality Report Page
Displays dataset profiling, missing data, column types, and quality flags.
Always available regardless of dataset type.
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

from frontend.utils.safe_render import safe_error_boundary
from frontend.utils.session_helpers import get_contract


def render() -> None:
    st.title("Data Quality Report")
    contract = get_contract()
    prof     = st.session_state.get("profile")

    if prof is None:
        st.info("Upload a dataset first.")
        return

    with safe_error_boundary("Quality KPIs"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Quality Score", f"{prof.overall_quality_score:.0f}/100")
        c2.metric(contract.row_label().title() if contract else "Rows", f"{prof.n_rows:,}")
        c3.metric("Columns", prof.n_cols)
        c4.metric("File Size", f"{prof.file_size_mb:.2f} MB")

    with safe_error_boundary("Quality Issues"):
        if contract and contract.quality_issues:
            st.subheader("Quality Issues")
            for qi in contract.quality_issues:
                st.warning(qi)

        if prof.quality_flags:
            with st.expander("All Quality Flags"):
                for f in prof.quality_flags:
                    st.warning(f)

    with safe_error_boundary("Column Type Distribution"):
        st.subheader("Column Type Distribution")
        tc = {
            "Numeric":     len(prof.numeric_cols),
            "Categorical": len(prof.categorical_cols),
            "Binary":      len(prof.binary_cols),
            "Datetime":    len(prof.datetime_cols),
            "Text":        len(prof.text_cols),
            "ID-like":     len(prof.id_cols),
        }
        tc = {k: v for k, v in tc.items() if v > 0}
        if tc:
            fig = px.pie(
                values=list(tc.values()), names=list(tc.keys()),
                title="Column Type Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)

    with safe_error_boundary("Missing Data"):
        if prof.missing_summary:
            st.subheader("Missing Data")
            mdf = pd.DataFrame(
                [(c, f"{v:.1%}") for c, v in prof.missing_summary.items()],
                columns=["Column", "Missing Rate"],
            )
            st.dataframe(mdf, use_container_width=True, hide_index=True)

    with safe_error_boundary("Column Profiles"):
        st.subheader("Column Profiles")
        rows = []
        for col, cp in prof.columns.items():
            row = {
                "Column":  col,
                "Type":    cp.inferred_type,
                "Missing": f"{cp.missing_rate:.0%}",
                "Unique":  cp.n_unique,
            }
            if cp.mean is not None:
                row["Mean"] = f"{cp.mean:.2f}"
                row["Std"]  = f"{cp.std:.2f}" if cp.std else "-"
            rows.append(row)
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
