"""
Metric Card Components
Dataset-aware KPI cards and metric displays.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from backend.core.dataset_contract import DatasetContract


def adaptive_dataset_kpis(
    contract: DatasetContract,
    n_rows: int,
    n_cols: int,
    quality: float,
    target: Optional[str],
) -> None:
    """
    Top-level KPI row — labels appropriate to dataset type.
    NEVER shows 'employees' for biosignal.
    """
    row_label = contract.row_label().title()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Total {row_label}", f"{n_rows:,}")
    c2.metric("Columns", n_cols)
    c3.metric("Quality Score", f"{quality:.0f}/100")

    if contract.is_biosignal:
        sig = contract.detected_signal_type or "Signal"
        c4.metric("Signal Type", sig)
    elif contract.target_available:
        c4.metric("Target Column", target or "—")
    else:
        c4.metric("Supervised Prediction", "Not available (no target)")

    if contract.is_biosignal:
        bio_prof = st.session_state.get("biosignal_profile")
        if bio_prof:
            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            r2c1.metric("Windows Analysed", f"{bio_prof.n_windows:,}")
            r2c2.metric("Signal Quality", f"{bio_prof.quality_score:.0f}/100")
            r2c3.metric("Anomaly Count", bio_prof.anomaly_count)
            r2c4.metric("Stress Proxy Level", bio_prof.stress_level_label)
