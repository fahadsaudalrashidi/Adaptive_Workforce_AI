"""
Adaptive Workforce Intelligence Engine v2.1 — Streamlit Frontend
Port 8510.  Run: py -3 -m streamlit run frontend/app.py --server.port 8510

DatasetContract controls EVERYTHING. No dashboard renders before reading the contract.
Biosignal datasets NEVER show employee metrics, attrition probabilities, or HR charts.

Safe-render utilities (call these instead of rendering directly):
  safe_render_employee_metrics()  — blocked for biosignal
  safe_render_attrition()         — blocked unless attrition_prediction allowed
  safe_render_department()        — blocked unless department_stability allowed

Pages:
  1. Adaptive Dataset Intelligence  — contract viewer, compatibility matrix, routing
  2. HR Attrition Analytics          — BLOCKED for biosignal/unknown
  3. Psychological Risk Intelligence — BLOCKED for biosignal
  4. Biosignal Intelligence          — ONLY for biosignal_timeseries
  5. Time-Series Early Warning       — available for TS + biosignal
  6. Department & Org Risk           — BLOCKED for biosignal/unknown
  7. Executive Insights & Actions    — contract-aware
  8. Model & AutoML Analytics        — BLOCKED for biosignal/unknown
  9. Data Quality Report             — always available
"""
from __future__ import annotations

import io
import sys
import logging
from pathlib import Path
from typing import Optional, Callable, Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Modular page imports ───────────────────────────────────────────────────────
try:
    from frontend.utils.demo_mode import get_visible_pages, is_demo_mode, mask_employee_id
    from frontend.components.governance_panel import (
        render_unified_confidence_panel as _render_unified_confidence_panel,
        render_feature_trust_panel as _render_feature_trust_panel,
    )
    import frontend.pages.adaptive_page      as _adaptive_mod
    import frontend.pages.hr_attrition_page  as _hr_attrition_mod
    import frontend.pages.department_page    as _department_mod
    import frontend.pages.insights_page      as _insights_mod
    import frontend.pages.biosignal_page     as _biosignal_mod
    import frontend.pages.explainability_page as _explainability_mod
    import frontend.pages.psychological_page as _psychological_mod
    import frontend.pages.timeseries_page    as _timeseries_mod
    import frontend.pages.model_page         as _model_mod
    import frontend.pages.quality_page       as _quality_mod
    _MODULAR = True
except ImportError:
    _MODULAR = False

from config.settings import (
    PLATFORM_NAME, PLATFORM_VERSION, REPORT_VERSION,
    DEFAULT_CURRENCY, CURRENCY_OPTIONS, CURRENCY_SYMBOLS,
    HUMAN_OVERSIGHT_DISCLAIMER,
)
from backend.core.confidence_governance import ConfidenceGovernor, UnifiedConfidenceReport, EXEC_READY, EXEC_CAUTION, EXEC_LIMITED, EXEC_NOT_READY
from backend.core.calibration_engine import CalibrationEngine, CalibrationQuality
from backend.core.feature_trustworthiness import FeatureTrustworthinessAssessor
from backend.core.dataset_contract import DatasetContract, ANALYSIS_LABELS
from backend.core.dataset_profiler import DatasetProfiler, load_dataframe
from backend.core.semantic_mapper import SemanticMapper
from backend.core.adaptive_router import AdaptiveRouter
from backend.core.data_healer import DataHealer
from backend.core.feature_factory import FeatureFactory
from backend.core.ml_router import MLRouter
from backend.core.risk_intelligence import (
    score_individuals, score_departments, score_organization, unsupervised_risk_scores,
)
from backend.core.insight_generator import InsightGenerator
from backend.core.biosignal_adapter import BiosignalAdapter, BiosignalProfile, DISCLAIMER
from backend.core.timeseries_engine import TimeSeriesEngine
from backend.core.explainability_engine import ExplainabilityEngine
from backend.core.ethical_ai import EthicalAIEngine
from backend.core.confidence_engine import ConfidenceEngine
from backend.core.report_generator import ReportGenerator
from backend.core.telemetry_engine import TelemetryEngine

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=f"{PLATFORM_NAME} v{PLATFORM_VERSION}",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

_PAGES = [
    "Adaptive Dataset Intelligence",
    "HR Attrition Analytics",
    "Psychological Risk Intelligence",
    "Biosignal Intelligence",
    "Time-Series Early Warning",
    "Department & Org Risk",
    "Executive Insights & Actions",
    "Model & AutoML Analytics",
    "Explainability & Governance",
    "Data Quality Report",
]

# ─────────────────────────────────────────────────────────────────────────────
# SINGLETONS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def _sng():
    return {
        "profiler":     DatasetProfiler(),
        "mapper":       SemanticMapper(),
        "router":       AdaptiveRouter(),
        "factory":      FeatureFactory(),
        "ml_router":    MLRouter(),
        "insight_gen":  InsightGenerator(),
        "biosignal":    BiosignalAdapter(),
        "ts_engine":    TimeSeriesEngine(),
        "explain_eng":  ExplainabilityEngine(),
        "ethical_eng":  EthicalAIEngine(),
        "conf_eng":     ConfidenceEngine(),
        "report_gen":   ReportGenerator(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def _init():
    defaults = {
        "df": None, "filename": "", "raw": None,
        "profile": None, "sem_map": None, "contract": None,
        "df_clean": None, "df_eng": None,
        "ml_result": None, "ind_risks": None, "dept_risks": None,
        "org_risk": None, "insight_report": None,
        "biosignal_profile": None, "ts_result": None,
        "analysis_done": False,
        "explain_report": None,
        "ethical_report": None,
        "confidence_profile": None,
        "exec_report": None,
        "telemetry": None,
        # Enterprise governance
        "unified_confidence": None,        # UnifiedConfidenceReport
        "feature_trust": None,             # FeatureTrustworthinessReport
        "currency": DEFAULT_CURRENCY,      # SAR / USD / AED / EUR
        "demo_mode": False,                # Company Demo Mode
        "mask_employee_ids": True,         # ID masking on by default
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _contract() -> Optional[DatasetContract]:
    return st.session_state.get("contract")


# ─────────────────────────────────────────────────────────────────────────────
# GUARD SYSTEM — read contract before rendering anything
# ─────────────────────────────────────────────────────────────────────────────

def _guard(analysis_key: str, page_name: str) -> bool:
    """
    Returns True if the analysis is allowed by the contract.
    Shows a styled block message and returns False if blocked.
    Call this as the FIRST statement in every page function.
    """
    c = _contract()
    if c is None:
        st.info("Upload a dataset from the sidebar, then run analysis.")
        return False
    if c.blocks(analysis_key):
        reason = next(
            (e.reason for e in c.compatibility_matrix if e.analysis_key == analysis_key),
            "Not applicable for this dataset type",
        )
        st.error(
            f"⛔ **{page_name}** is not available for this dataset.\n\n"
            f"**Dataset type**: {c.dataset_type.replace('_', ' ').title()}  \n"
            f"**Row unit**: {c.row_label()}  \n"
            f"**Reason**: {reason}"
        )
        if c.is_biosignal:
            st.info(
                "This file contains physiological signal data (NOT employee records). "
                "Navigate to **Biosignal Intelligence** for the appropriate analysis."
            )
        return False
    return True


def _require_analysis(page_key: str = "") -> bool:
    if not st.session_state.get("analysis_done"):
        st.info("Run analysis from the **Adaptive Dataset Intelligence** page first.")
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# SAFE-RENDER UTILITIES — wrap every HR/employee section in these
# ─────────────────────────────────────────────────────────────────────────────

def safe_render_employee_metrics(render_fn: Callable[[], Any]) -> None:
    """
    Execute render_fn ONLY if the loaded dataset has employee-level rows.
    For biosignal / unknown datasets, shows a clear block message instead.
    """
    c = _contract()
    if c is None:
        return
    if c.is_biosignal or c.row_unit == "signal_samples":
        st.warning(
            f"⛔ Employee metrics are not applicable for **{c.dataset_type.replace('_',' ').title()}** datasets.  \n"
            f"Rows in this file represent **{c.row_label()}**, not employees."
        )
        return
    render_fn()


def safe_render_attrition(render_fn: Callable[[], Any]) -> None:
    """
    Execute render_fn ONLY if attrition_prediction is allowed by the contract.
    """
    c = _contract()
    if c is None:
        return
    if c.blocks("attrition_prediction"):
        reason = next(
            (e.reason for e in c.compatibility_matrix if e.analysis_key == "attrition_prediction"),
            "Attrition prediction not applicable",
        )
        st.warning(f"⛔ Attrition analysis blocked — {reason}")
        return
    render_fn()


def safe_render_department(render_fn: Callable[[], Any]) -> None:
    """
    Execute render_fn ONLY if department_stability is allowed by the contract.
    """
    c = _contract()
    if c is None:
        return
    if c.blocks("department_stability"):
        reason = next(
            (e.reason for e in c.compatibility_matrix if e.analysis_key == "department_stability"),
            "Department analysis not applicable",
        )
        st.warning(f"⛔ Department analysis blocked — {reason}")
        return
    render_fn()


def safe_render_retention_roi(render_fn: Callable[[], Any]) -> None:
    """
    Execute render_fn ONLY if retention_roi is allowed.
    Specifically guards against showing replacement cost for biosignal data.
    """
    c = _contract()
    if c is None:
        return
    if c.blocks("retention_roi"):
        if c.is_biosignal:
            st.warning("⛔ Replacement cost / retention ROI requires employee salary data. "
                       "This is a physiological signal dataset — no salary data present.")
        else:
            st.warning("⛔ Retention ROI requires salary + attrition data.")
        return
    render_fn()


# ─────────────────────────────────────────────────────────────────────────────
# SAFE DATAFRAME RENDERING — jinja2 guard
# ─────────────────────────────────────────────────────────────────────────────

def safe_styled_dataframe(df: pd.DataFrame, styler_func=None, **kwargs) -> None:
    """
    Render a DataFrame with optional row styling.
    Falls back to plain st.dataframe if jinja2 is missing or styling fails.
    """
    if styler_func is not None:
        try:
            st.dataframe(df.style.apply(styler_func, axis=1), **kwargs)
            return
        except Exception as exc:
            msg = str(exc).lower()
            if "jinja2" in msg or "style" in msg or "styler" in msg:
                st.dataframe(df, **kwargs)
                st.caption("Row colouring disabled — install jinja2 to enable: `pip install jinja2`")
                return
            raise
    st.dataframe(df, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# DATASET-AWARE METRIC CARD
# ─────────────────────────────────────────────────────────────────────────────

def _adaptive_metric_card(contract: DatasetContract, n_rows: int, n_cols: int,
                           quality: float, target: Optional[str]):
    """
    Renders the top-level KPI row with labels appropriate to the dataset type.
    NEVER shows "employees" for biosignal; shows "signal samples" instead.
    """
    row_label = contract.row_label().title()   # "Signal Samples" / "Employees" / etc.

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

    # Second row for biosignal — signal-specific metrics
    if contract.is_biosignal:
        bio_prof: Optional[BiosignalProfile] = st.session_state.get("biosignal_profile")
        if bio_prof:
            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            r2c1.metric("Windows Analysed", f"{bio_prof.n_windows:,}")
            r2c2.metric("Signal Quality", f"{bio_prof.quality_score:.0f}/100")
            r2c3.metric("Anomaly Count", bio_prof.anomaly_count)
            r2c4.metric("Stress Proxy Level", bio_prof.stress_level_label)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

def _sidebar() -> str:
    with st.sidebar:
        st.markdown(f"## {PLATFORM_NAME}")
        st.caption(f"v{PLATFORM_VERSION} · Enterprise AI Decision-Support")
        st.divider()

        # ── Company Demo Mode toggle ──────────────────────────────────────────
        demo = st.toggle("Company Demo Mode", value=st.session_state.get("demo_mode", False),
                         help="Hides technical debug panels for executive presentations.")
        st.session_state["demo_mode"] = demo

        if demo:
            demo_pages = [
                "Adaptive Dataset Intelligence",
                "HR Attrition Analytics",
                "Department & Org Risk",
                "Executive Insights & Actions",
                "Explainability & Governance",
                "Data Quality Report",
            ]
            st.caption("Demo mode: showing executive pages only.")
            page = st.radio("Navigation", demo_pages, label_visibility="collapsed")
        else:
            page = st.radio("Navigation", _PAGES, label_visibility="collapsed")
        st.divider()

        st.markdown("### Upload Dataset")
        uploaded = st.file_uploader(
            "CSV · XLSX · JSON · Parquet",
            type=["csv", "xlsx", "xls", "json", "parquet", "pkl", "feather"],
        )
        if uploaded:
            _handle_upload(uploaded)

        # ── Currency selector ─────────────────────────────────────────────────
        st.markdown("### Settings")
        curr_idx = CURRENCY_OPTIONS.index(st.session_state.get("currency", DEFAULT_CURRENCY)) \
                   if st.session_state.get("currency", DEFAULT_CURRENCY) in CURRENCY_OPTIONS else 0
        currency = st.selectbox("Currency", CURRENCY_OPTIONS, index=curr_idx)
        st.session_state["currency"] = currency

        mask_ids = st.checkbox("Mask Employee IDs", value=st.session_state.get("mask_employee_ids", True),
                               help="Show Employee #001 instead of raw identifiers in executive view.")
        st.session_state["mask_employee_ids"] = mask_ids

        c = _contract()
        if c:
            _type_badge(c)
            prof = st.session_state.get("profile")
            if prof:
                st.caption(
                    f"**{prof.n_rows:,}** {c.row_label()} · {prof.n_cols} columns"
                )
            if c.is_biosignal:
                st.error("BIOSIGNAL — HR analytics blocked")
                st.caption("Rows = physiological signal samples, NOT employees")
            elif not c.target_available:
                st.warning("No attrition target — unsupervised mode")

            # Unified confidence badge (not sandbox health — that's technical)
            ucr: Optional[UnifiedConfidenceReport] = st.session_state.get("unified_confidence")
            if ucr:
                _badge_colors = {
                    EXEC_READY:    "#16a34a",
                    EXEC_CAUTION:  "#d97706",
                    EXEC_LIMITED:  "#ea580c",
                    EXEC_NOT_READY: "#dc2626",
                }
                _bc = _badge_colors.get(ucr.executive_readiness, "#6b7280")
                st.markdown(
                    f'<div style="background:{_bc}22;border-left:4px solid {_bc};'
                    f'padding:6px 10px;border-radius:4px;font-size:0.82rem;margin-top:4px">'
                    f'<strong style="color:{_bc}">AI Readiness: {ucr.executive_readiness}</strong><br>'
                    f'<span style="color:{_bc}">Analysis: {ucr.analysis_confidence.band} '
                    f'({ucr.analysis_confidence.score:.0%})</span></div>',
                    unsafe_allow_html=True,
                )
            elif not demo:
                # Show sandbox health only in technical mode
                if c.sandbox_report:
                    sb = c.sandbox_report
                    health_pct = int(sb.dataset_health_score * 100)
                    if health_pct >= 75:
                        st.success(f"Sandbox: {health_pct}% healthy")
                    elif health_pct >= 50:
                        st.warning(f"Sandbox: {health_pct}% · {len(sb.globally_blocked)} blocked")
                    else:
                        st.error(f"Sandbox: {health_pct}% · {len(sb.critical_failures)} critical")

        st.divider()
        if not demo:
            with st.expander("System Controls"):
                if st.button("Clear All Cache", use_container_width=True):
                    st.cache_data.clear()
                    st.cache_resource.clear()
                if st.button("Reset Session", use_container_width=True):
                    for k in list(st.session_state.keys()):
                        del st.session_state[k]
                    st.rerun()

    return page


def _type_badge(c: DatasetContract):
    colors = {
        "hr_attrition":         ("#1e40af", "#dbeafe"),
        "hr_workforce":         ("#1e3a5f", "#cfe2ff"),
        "biosignal_timeseries": ("#065f46", "#d1fae5"),
        "psychological_survey": ("#7c3aed", "#ede9fe"),
        "burnout_survey":       ("#9d174d", "#fce7f3"),
        "generic_timeseries":   ("#92400e", "#fef3c7"),
        "mixed_enterprise":     ("#be185d", "#fce7f3"),
        "unknown":              ("#374151", "#f3f4f6"),
    }
    bg, fg = colors.get(c.dataset_type, ("#374151", "#f3f4f6"))
    st.markdown(
        f"""<div style="background:{fg};border-left:4px solid {bg};padding:0.5rem 0.8rem;
        border-radius:6px;margin:0.4rem 0">
        <span style="color:{bg};font-weight:700;font-size:0.85rem">
        {c.dataset_type.replace('_', ' ').upper()}</span><br>
        <span style="color:#374151;font-size:0.75rem">
        Confidence: {c.confidence:.0%}</span>
        </div>""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD HANDLER
# ─────────────────────────────────────────────────────────────────────────────

def _handle_upload(uploaded):
    if uploaded.name == st.session_state.get("filename"):
        return
    s = _sng()
    raw = uploaded.read()
    fn  = uploaded.name
    with st.spinner(f"Profiling {fn}…"):
        try:
            df, _, _  = load_dataframe(raw, fn)
            prof      = s["profiler"].profile(io.BytesIO(raw), fn)
            sem_map   = s["mapper"].map(df)
            contract  = s["router"].route(df, fn)

            tel = TelemetryEngine(persist_to_db=False)
            tel.log_upload(fn, n_rows=len(df), n_cols=len(df.columns))
            if contract.modality_result:
                mr = contract.modality_result
                tel.log_modality(mr.modality.value, mr.confidence, mr.sub_modality, mr.validity_score)
            if contract.routing_confidence:
                rc = contract.routing_confidence
                tel.log_confidence(contract.dataset_type, rc.overall_confidence, rc.confidence_band, rc.suppressed_analyses)
            if contract.semantic_map_v2:
                sm = contract.semantic_map_v2
                _sm_cols = getattr(sm, "columns", None) or {}
                tel.log_semantic_map(
                    n_cols=len(_sm_cols),
                    dominant_role=sm.dominant_role if sm.dominant_role else "unknown",
                    coherence=sm.schema_coherence,
                    target_candidates=sm.target_candidates,
                )
            if contract.sandbox_report:
                sb = contract.sandbox_report
                tel.log_sandbox(
                    n_available=len(sb.globally_available),
                    n_blocked=len(sb.globally_blocked),
                    health=sb.dataset_health_score,
                    critical_failures=sb.critical_failures,
                )

            st.session_state.update({
                "df": df, "filename": fn, "raw": raw,
                "profile": prof, "sem_map": sem_map,
                "contract": contract, "analysis_done": False,
                "ml_result": None, "ind_risks": None, "dept_risks": None,
                "org_risk": None, "insight_report": None,
                "biosignal_profile": None, "ts_result": None,
                "df_clean": None, "df_eng": None,
                "explain_report": None, "ethical_report": None,
                "confidence_profile": None, "exec_report": None,
                "telemetry": tel,
            })
        except Exception as e:
            st.error(f"Failed to load '{fn}': {e}")
            logger.exception("Upload error")


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def _run_analysis(target_override: Optional[str] = None):
    s        = _sng()
    df       = st.session_state["df"]
    contract = st.session_state["contract"]
    sem_map  = st.session_state["sem_map"]
    filename = st.session_state["filename"]

    if df is None or contract is None:
        st.warning("Upload a dataset first.")
        return

    with st.spinner("Running adaptive analysis pipeline…"):
        try:
            # ── BIOSIGNAL BRANCH ──────────────────────────────────────────────
            if contract.is_biosignal:
                sig_type = contract.detected_signal_type or "unknown"
                bio_prof = s["biosignal"].analyse(df, sig_type, filename)
                st.session_state["biosignal_profile"] = bio_prof

                # Time-series on window stress scores
                wf = bio_prof.window_features_df
                if wf is not None and "StressSignalScore" in wf.columns:
                    ts_res = s["ts_engine"].analyse(
                        wf, metric_col="StressSignalScore", time_col="SampleStart",
                    )
                    st.session_state["ts_result"] = ts_res

                insight_rep = s["insight_gen"].generate(
                    dataset_type="biosignal_timeseries",
                    quality_score=bio_prof.quality_score,
                    n_rows=bio_prof.n_samples,
                    n_cols=len(df.columns),
                    biosignal_context={
                        "signal_type":   bio_prof.signal_type,
                        "global_stats":  bio_prof.global_stats,
                        "stress_score":  bio_prof.stress_signal_score,
                        "quality_score": bio_prof.quality_score,
                        "anomaly_count": bio_prof.anomaly_count,
                    },
                )
                st.session_state["insight_report"] = insight_rep

                # Explainability + confidence for biosignal
                try:
                    wf_feat = bio_prof.window_features_df
                    top_feats = []
                    if wf_feat is not None:
                        numeric_cols = wf_feat.select_dtypes(include=[np.number]).columns.tolist()
                        if numeric_cols:
                            stds = wf_feat[numeric_cols].std().sort_values(ascending=False)
                            top_feats = [{"feature_name": c, "plain_english": f"Variability in {c}"} for c in stds.index[:6]]

                    explain_rep = s["explain_eng"].explain_biosignal(
                        signal_type=bio_prof.signal_type,
                        n_samples=bio_prof.n_samples,
                        n_windows=bio_prof.n_windows,
                        quality_score=bio_prof.quality_score / 100.0,
                        stress_score=bio_prof.stress_signal_score,
                        anomaly_count=bio_prof.anomaly_count,
                    )
                    conf_prof = s["conf_eng"].assess_signal_quality(
                        n_samples=bio_prof.n_samples,
                        n_windows=bio_prof.n_windows,
                        missing_pct=bio_prof.missing_rate,
                        anomaly_pct=bio_prof.anomaly_count / max(bio_prof.n_windows, 1),
                        signal_type=bio_prof.signal_type,
                    )
                    exec_rep = s["report_gen"].generate_biosignal_report(
                        signal_type=bio_prof.signal_type,
                        n_samples=bio_prof.n_samples,
                        n_windows=bio_prof.n_windows,
                        quality_score=bio_prof.quality_score / 100.0,
                        stress_score=bio_prof.stress_signal_score,
                        fatigue_score=bio_prof.fatigue_signal_score,
                        anomaly_count=bio_prof.anomaly_count,
                        anomaly_pct=bio_prof.anomaly_count / max(bio_prof.n_windows, 1),
                        volatility_mean=bio_prof.signal_volatility_score,
                        top_features=top_feats,
                        disclaimer=bio_prof.disclaimer,
                    )
                    st.session_state["explain_report"]   = explain_rep
                    st.session_state["confidence_profile"] = conf_prof
                    st.session_state["exec_report"]      = exec_rep
                except Exception:
                    pass

                st.session_state["analysis_done"]  = True
                return

            # ── HR / SURVEY / GENERIC BRANCH ─────────────────────────────────
            target = target_override or contract.target_column or sem_map.target_col
            healer = DataHealer()
            df_clean, _ = healer.fit_transform(df, sem_map, target)
            df_eng, _ = s["factory"].engineer(df_clean, sem_map, contract.dataset_type, target)
            feature_names = [c for c in df_eng.columns if c != target]

            if contract.allows("attrition_prediction") and target and target in df_eng.columns:
                ml_res = s["ml_router"].train(df_eng, feature_names, target, contract.dataset_type)
                probs  = s["ml_router"].predict_proba(df_eng, ml_res)
            else:
                ml_res = None
                probs  = unsupervised_risk_scores(df_eng, sem_map)

            _currency = st.session_state.get("currency", DEFAULT_CURRENCY)
            ind_risks  = score_individuals(df_eng, probs, sem_map, currency=_currency)
            dept_risks = score_departments(df_eng, probs, ind_risks, sem_map, currency=_currency)
            org_risk   = score_organization(ind_risks, dept_risks, currency=_currency)

            prof   = st.session_state["profile"]
            miss_p = float(np.mean(list(prof.missing_summary.values()))) if prof.missing_summary else 0.0
            auc    = ml_res.best_metric_value if ml_res and ml_res.best_metric_name == "auc" else 0.0

            insight_rep = s["insight_gen"].generate(
                dataset_type=contract.dataset_type,
                org_risk=org_risk,
                model_auc=auc,
                quality_score=prof.overall_quality_score,
                n_rows=prof.n_rows,
                n_cols=prof.n_cols,
                missing_pct=miss_p,
                n_numeric=len(prof.numeric_cols),
                n_categorical=len(prof.categorical_cols),
                currency=st.session_state.get("currency", DEFAULT_CURRENCY),
            )

            if "RetentionRisk" in df_eng.columns:
                ts_res = s["ts_engine"].analyse(
                    df_eng, metric_col="RetentionRisk", synthetic_fallback=True,
                )
                st.session_state["ts_result"] = ts_res

            # ── Explainability + Ethical AI + Confidence ────────────────────
            prof       = st.session_state["profile"]
            _quality   = contract.quality_score / 100.0
            _auc       = ml_res.best_metric_value if (ml_res and ml_res.best_metric_name == "auc") else 0.65
            _n_rows    = prof.n_rows if prof else len(df)
            _miss_p    = float(np.mean(list(prof.missing_summary.values()))) if (prof and prof.missing_summary) else 0.0

            explain_rep     = None
            ethical_rep     = None
            conf_profile    = None
            exec_report_obj = None

            try:
                # Feature facts from ml_result
                best_model_result = ml_res.models.get(ml_res.best_model_name) if ml_res and ml_res.models else None
                feat_importances  = best_model_result.feature_importances if best_model_result else {}
                _fi_list = [
                    {"feature_name": k, "importance_score": v, "direction": "increases_risk", "plain_english": f"{k} influences the prediction"}
                    for k, v in list(feat_importances.items())[:10]
                ] if feat_importances else []

                explain_rep = s["explain_eng"].explain_hr(
                    ml_result=ml_res,
                    df_eng=df_eng,
                    feature_names=feature_names,
                    target_col=target,
                    dataset_type=contract.dataset_type,
                    dataset_subtype=contract.dataset_subtype,
                    n_rows_input=_n_rows,
                    n_rows_healed=len(df_clean),
                    n_features_raw=len(df.columns),
                    data_quality_score=_quality,
                    training_mode="AutoML" if ml_res else "Unsupervised",
                    preprocessing_steps=[
                        "Column mapping", "Data healing", "Feature engineering",
                        "Train/test split", "SMOTE inside CV folds", "AutoML training",
                    ],
                )
            except Exception:
                pass

            try:
                ethical_rep = s["ethical_eng"].audit_bias(
                    df=df_eng,
                    target_col=target,
                    positive_label="Yes",
                )
                gov = s["ethical_eng"].govern_prediction(
                    prediction_type="attrition",
                    raw_confidence=_auc,
                    n_samples=_n_rows,
                    data_quality_score=_quality,
                    auc_score=_auc,
                    protected_bias_risk=ethical_rep.overall_risk_level,
                )
                ethical_report_full = s["ethical_eng"].generate_ethical_report(ethical_rep, [gov])
                ethical_rep = ethical_report_full
            except Exception:
                pass

            try:
                conf_profile = s["conf_eng"].quick_profile(
                    auc_score=_auc,
                    n_samples=_n_rows,
                    data_quality_score=_quality,
                )
            except Exception:
                pass

            # ── Feature Trustworthiness ──────────────────────────────────────
            feat_trust = None
            try:
                _best_mr   = ml_res.models.get(ml_res.best_model_name) if ml_res and ml_res.models else None
                _fi_dict   = _best_mr.feature_importances if _best_mr else {}
                feat_trust = FeatureTrustworthinessAssessor().assess(
                    df=df_eng,
                    feature_names=feature_names,
                    target_col=target,
                    feature_importances=_fi_dict,
                )
            except Exception:
                pass

            # ── Calibration Quality ──────────────────────────────────────────
            calibration_rep = None
            try:
                if ml_res is not None and target and target in df_eng.columns:
                    _best_model_r = (ml_res.models.get(ml_res.best_model_name)
                                     if ml_res.models else None)
                    _oof_preds = getattr(_best_model_r, "oof_predictions", None) if _best_model_r else None
                    if _oof_preds is not None and len(_oof_preds) > 0:
                        _y_true_raw = df_eng[target].values
                        _y_true_bin = (
                            (_y_true_raw == "Yes").astype(float)
                            if _y_true_raw.dtype == object or str(_y_true_raw.dtype).startswith("string")
                            else _y_true_raw.astype(float)
                        )
                        calibration_rep = CalibrationEngine().evaluate(
                            y_true=_y_true_bin,
                            y_prob=np.asarray(_oof_preds, dtype=float),
                        )
            except Exception:
                pass

            try:
                _bias_risk  = ethical_rep.bias_audit.overall_risk_level if (ethical_rep and hasattr(ethical_rep, "bias_audit")) else "acceptable"
                _gov_conf   = conf_profile.overall_confidence if conf_profile else _auc
                _rpt_leak   = getattr(ml_res, "leakage_report",    None) if ml_res else None
                _rpt_val    = getattr(ml_res, "validation_report",  None) if ml_res else None
                exec_report_obj = s["report_gen"].generate_hr_report(
                    dataset_type=contract.dataset_type,
                    dataset_subtype=contract.dataset_subtype,
                    n_rows=_n_rows,
                    n_features=len(feature_names),
                    data_quality_score=_quality,
                    target_column=target,
                    model_type=ml_res.best_model_name if ml_res else "Unsupervised",
                    auc_score=_auc,
                    training_mode="AutoML" if ml_res else "Unsupervised",
                    top_features=_fi_list,
                    attrition_rate=org_risk.overall_attrition_risk if org_risk else None,
                    risk_distribution={
                        "High Risk": org_risk.high_risk_employees if org_risk else 0,
                        "Lower Risk": (org_risk.total_employees - org_risk.high_risk_employees) if org_risk else 0,
                    } if org_risk else None,
                    bias_risk_level=_bias_risk,
                    ethical_disclaimer=(
                        "This report is generated by an automated AI system. "
                        "All predictions must be reviewed by qualified HR professionals "
                        "before informing personnel decisions."
                    ),
                    provenance_steps=[
                        f"Raw data: {_n_rows:,} rows × {len(df.columns)} columns",
                        f"Data healing: {len(df_clean):,} rows after cleaning",
                        f"Feature engineering: {len(feature_names)} features",
                        f"Model: {ml_res.best_model_name if ml_res else 'Unsupervised'}, AUC={_auc:.3f}",
                        "Confidence governed and bias-audited",
                    ],
                    caveats=conf_profile.statistical_validity.caveats if conf_profile else [],
                    governed_confidence=_gov_conf,
                    currency=st.session_state.get("currency", DEFAULT_CURRENCY),
                    original_auc=_auc,
                    governed_auc=_rpt_val.governed_auc if _rpt_val else _auc,
                    leakage_risk_score=_rpt_leak.leakage_risk_score if _rpt_leak else 0.0,
                    leakage_n_critical=_rpt_leak.n_critical if _rpt_leak else 0,
                    leakage_n_high=_rpt_leak.n_high if _rpt_leak else 0,
                    calibration_quality_label=(calibration_rep.quality.value
                                               if calibration_rep else "Not Evaluated"),
                    brier_score=calibration_rep.brier_score if calibration_rep else None,
                    calibration_ece=calibration_rep.ece if calibration_rep else None,
                    model_reliability_score=None,
                )
            except Exception:
                pass

            # ── Unified Confidence Governance ────────────────────────────────
            unified_conf = None
            try:
                _leak_rep  = getattr(ml_res, "leakage_report",  None) if ml_res else None
                _val_rep   = getattr(ml_res, "validation_report", None) if ml_res else None
                _rc_raw    = (contract.routing_confidence.overall_confidence
                              if contract.routing_confidence else 0.70)
                _rc_locked = (contract.routing_confidence.routing_locked
                              if contract.routing_confidence else False)
                _gov_auc   = (_val_rep.governed_auc if _val_rep else _auc)
                _orig_auc  = _auc
                _has_burn  = any(r.burnout_risk is not None for r in (ind_risks or []))
                _has_eng   = any(r.engagement_risk is not None for r in (ind_risks or []))

                # Extract oof_fold_std and train/test gap from validation checks
                _oof_fold_std: Optional[float] = None
                _train_test_gap: Optional[float] = None
                if _val_rep and getattr(_val_rep, "checks", None):
                    for _chk in _val_rep.checks:
                        if _chk.check_name == "FOLD_STABILITY" and _chk.value is not None:
                            _oof_fold_std = float(_chk.value)
                        elif _chk.check_name == "HOLDOUT_VALIDITY" and _chk.value is not None:
                            # value = abs(gap); FAIL/WARN means overfitting (negative gap)
                            _abs_gap = float(_chk.value)
                            _train_test_gap = -_abs_gap if _chk.severity in ("FAIL", "WARN") else _abs_gap

                # Feature trust scores from FeatureTrustworthinessReport
                _feat_trust_score: Optional[float] = None
                _feat_dom_flag = False
                if feat_trust:
                    _feat_dom_flag = bool(feat_trust.has_dominance_warning)
                    _trust_map = {"Reliable": 0.90, "Caution": 0.60, "High Risk": 0.30}
                    _feat_trust_score = _trust_map.get(feat_trust.overall_trust, 0.70)

                unified_conf = ConfidenceGovernor().build(
                    profiler_quality_score  = prof.overall_quality_score if prof else 70.0,
                    missing_pct             = _miss_p,
                    n_rows                  = _n_rows,
                    n_cols                  = len(df.columns),
                    routing_type            = contract.dataset_type,
                    routing_confidence_raw  = _rc_raw,
                    routing_locked          = _rc_locked,
                    has_ml_model            = ml_res is not None,
                    original_auc            = _orig_auc,
                    governed_auc            = _gov_auc,
                    leakage_risk_score      = _leak_rep.leakage_risk_score if _leak_rep else 0.0,
                    leakage_n_critical      = _leak_rep.n_critical if _leak_rep else 0,
                    leakage_n_high          = _leak_rep.n_high if _leak_rep else 0,
                    is_trustworthy          = _leak_rep.is_trustworthy if _leak_rep else True,
                    validation_overall_status = _val_rep.overall_status if _val_rep else "VALID",
                    validation_n_fail       = _val_rep.n_fail if _val_rep else 0,
                    oof_fold_std            = _oof_fold_std,
                    brier_score             = calibration_rep.brier_score if calibration_rep else None,
                    calibration_ece         = calibration_rep.ece if calibration_rep else None,
                    feature_trust_score     = _feat_trust_score,
                    feature_dominance_flag  = _feat_dom_flag,
                    train_test_gap          = _train_test_gap,
                    class_balance_ratio     = (
                        float((df_eng[target] == df_eng[target].value_counts().idxmin()).mean())
                        if ml_res and target and target in df_eng.columns
                        else None
                    ),
                    deployment_safe         = _val_rep.deployment_safe if _val_rep else None,
                    has_burnout_evidence    = _has_burn,
                    has_engagement_evidence = _has_eng,
                )
            except Exception:
                pass

            # Log analysis events to telemetry
            tel = st.session_state.get("telemetry")
            if tel and contract.sandbox_report:
                sb = contract.sandbox_report
                for key in sb.globally_blocked:
                    tel.log_guard_result(key, False, [f"Sandbox blocked: {key}"], [])
                for key in sb.globally_available:
                    tel.log_guard_result(key, True, [], [])
            if tel and ml_res:
                _auc_log = ml_res.best_metric_value if ml_res.best_metric_name == "auc" else 0.0
                tel.log_analysis("attrition_prediction", 0.0, True, ml_res.best_model_name, _auc_log)

            st.session_state.update({
                "df_clean": df_clean, "df_eng": df_eng,
                "ml_result": ml_res, "ind_risks": ind_risks,
                "dept_risks": dept_risks, "org_risk": org_risk,
                "insight_report": insight_rep, "analysis_done": True,
                "explain_report": explain_rep,
                "ethical_report": ethical_rep,
                "confidence_profile": conf_profile,
                "exec_report": exec_report_obj,
                "unified_confidence": unified_conf,
                "feature_trust": feat_trust,
                "calibration_report": calibration_rep,
            })

        except Exception as e:
            st.error(f"Analysis failed: {e}")
            logger.exception("Analysis error")


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED CONFIDENCE GOVERNANCE PANEL
# ─────────────────────────────────────────────────────────────────────────────

def _render_unified_confidence_panel():
    """AI Reliability & Governance Summary — shown prominently in executive pages."""
    ucr: Optional[UnifiedConfidenceReport] = st.session_state.get("unified_confidence")
    if ucr is None:
        st.info("Run analysis to see the AI reliability summary.")
        return

    _ready_colors = {
        EXEC_READY:     ("#16a34a", "#f0fdf4"),
        EXEC_CAUTION:   ("#d97706", "#fffbeb"),
        EXEC_LIMITED:   ("#ea580c", "#fff7ed"),
        EXEC_NOT_READY: ("#dc2626", "#fef2f2"),
    }
    _band_colors = {
        "High":       "#16a34a",
        "Moderate":   "#d97706",
        "Low":        "#ea580c",
        "Unreliable": "#dc2626",
        "N/A":        "#6b7280",
    }
    rc, rbg = _ready_colors.get(ucr.executive_readiness, ("#6b7280", "#f9fafb"))
    st.markdown(
        f"""<div style="background:{rbg};border-left:6px solid {rc};
        padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
        <h3 style="color:{rc};margin:0">AI Readiness: {ucr.executive_readiness}</h3>
        <p style="color:{rc};margin:0.5rem 0 0 0">{ucr.executive_reason}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    dims = [ucr.data_quality, ucr.routing_confidence, ucr.model_reliability,
            ucr.analysis_confidence]
    dim_labels = ["Data Quality", "Routing", "Model Reliability", "Analysis"]
    for i, (col, dim, lbl) in enumerate(zip(cols[:4], dims, dim_labels)):
        bc = _band_colors.get(dim.band, "#6b7280")
        col.markdown(
            f'<div style="text-align:center;padding:8px;border:1px solid {bc};border-radius:6px">'
            f'<div style="font-size:1.3rem;font-weight:700;color:{bc}">{dim.score:.0%}</div>'
            f'<div style="font-size:0.72rem;color:{bc};font-weight:600">{dim.band}</div>'
            f'<div style="font-size:0.7rem;color:#6b7280;margin-top:2px">{lbl}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    # Leakage risk in 5th column
    lr_color = "#dc2626" if ucr.leakage_risk_score > 0.3 else "#d97706" if ucr.leakage_risk_score > 0.1 else "#16a34a"
    cols[4].markdown(
        f'<div style="text-align:center;padding:8px;border:1px solid {lr_color};border-radius:6px">'
        f'<div style="font-size:1.3rem;font-weight:700;color:{lr_color}">{ucr.leakage_risk_score:.0%}</div>'
        f'<div style="font-size:0.72rem;color:{lr_color};font-weight:600">'
        f'{"High" if ucr.leakage_risk_score>0.3 else "Low"}</div>'
        f'<div style="font-size:0.7rem;color:#6b7280;margin-top:2px">Leakage Risk</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if ucr.caveats:
        with st.expander("Confidence Caveats & Explanations"):
            for caveat in ucr.caveats:
                st.warning(caveat)
            # Show dimension explanations
            for dim in dims:
                if dim.degraded_by:
                    st.caption(f"**{dim.label}:** {dim.reason}")

    # Human oversight disclaimer
    st.markdown(
        f'<div style="background:#fef2f2;border-left:4px solid #dc2626;'
        f'padding:8px 12px;border-radius:4px;font-size:0.82rem;margin-top:8px">'
        f'<strong>Human Oversight Required:</strong> {HUMAN_OVERSIGHT_DISCLAIMER}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_feature_trust_panel():
    """Feature Trustworthiness Assessment — shows cardinality/dominance warnings."""
    ft = st.session_state.get("feature_trust")
    if ft is None:
        return  # Silent — only rendered for HR datasets with a trained model

    _trust_colors = {
        "Reliable":               "#16a34a",
        "Interpret with Caution": "#d97706",
        "High Risk — Validate":   "#dc2626",
    }
    tc = _trust_colors.get(ft.overall_trust, "#6b7280")
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
            "Some features require careful interpretation. See the table below for details. "
            "Associations shown are statistical patterns, not causal relationships."
        )
    if ft.downgrade_model_reliability and ft.downgrade_reason:
        st.error(f"Model reliability may be overstated: {ft.downgrade_reason}")

    if ft.assessments:
        rows = []
        for a in ft.assessments[:15]:
            rows.append({
                "Feature":          a.feature_name,
                "Importance":       f"{a.importance_share:.0%}",
                "Type":             a.dtype.title(),
                "Unique Values":    a.n_unique,
                "Cardinality Risk": a.cardinality_risk,
                "Dominance":        a.dominance_risk,
                "Trust Level":      a.trust_level,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Show top feature associative note
        top = ft.assessments[0]
        st.info(f"**Top predictor '{top.feature_name}':** {top.associative_note}")

    if ft.recommendations:
        with st.expander("Feature Recommendations"):
            for rec in ft.recommendations:
                st.write(f"- {rec}")


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTIVE PDF ROUTING
# ─────────────────────────────────────────────────────────────────────────────

def _render_pdf_section():
    """
    Dataset-type-aware PDF/export section.
    HR → Workforce Intelligence Report
    Biosignal → Biosignal Stress Intelligence Report
    Unknown → Dataset Profiling Report
    """
    contract = _contract()
    if contract is None:
        st.info("Upload a dataset to enable export.")
        return

    if not st.session_state.get("analysis_done"):
        st.info("Run analysis first.")
        return

    st.subheader("📄 Export Report")

    if contract.is_biosignal:
        st.info("**Biosignal Stress Intelligence Report** will be generated.")
        _export_biosignal_report()

    elif contract.is_hr and contract.allows("pdf_report"):
        st.info("**Workforce Intelligence PDF Report** will be generated.")
        _export_hr_report()

    elif contract.is_survey:
        st.info("**Psychological Risk Report** will be generated.")
        _export_survey_report()

    else:
        st.info("**Dataset Profiling Report** will be generated.")
        _export_profiling_report()


def _build_csv_export() -> bytes:
    contract = _contract()
    df_eng   = st.session_state.get("df_eng")
    bio_prof = st.session_state.get("biosignal_profile")

    if contract and contract.is_biosignal and bio_prof and bio_prof.window_features_df is not None:
        return bio_prof.window_features_df.to_csv(index=False).encode("utf-8")
    elif df_eng is not None:
        return df_eng.to_csv(index=False).encode("utf-8")
    return b""


def _export_biosignal_report():
    bio_prof = st.session_state.get("biosignal_profile")
    contract = _contract()
    if bio_prof is None:
        st.warning("No biosignal profile available.")
        return

    lines = [
        "=" * 60,
        "BIOSIGNAL STRESS INTELLIGENCE REPORT",
        f"Signal Type: {bio_prof.canonical_name}",
        f"Row Unit: {bio_prof.row_unit}",
        "=" * 60,
        "",
        "NON-CLINICAL DISCLAIMER:",
        bio_prof.disclaimer,
        "",
        "SIGNAL OVERVIEW:",
        f"  Total Signal Samples: {bio_prof.n_samples:,}",
        f"  Windows Analysed:     {bio_prof.n_windows:,}",
        f"  Duration:             {bio_prof.duration_seconds:.0f} seconds",
        f"  Sampling Frequency:   {bio_prof.estimated_fs:.1f} Hz",
        f"  Missing Rate:         {bio_prof.missing_rate:.1%}",
        "",
        "SIGNAL QUALITY:",
        f"  Quality Score:  {bio_prof.quality_score:.0f}/100",
        f"  Anomaly Count:  {bio_prof.anomaly_count}",
        "",
        "PHYSIOLOGICAL STRESS PROXY:",
        f"  Stress Level:          {bio_prof.stress_level_label}",
        f"  Stress Signal Score:   {bio_prof.stress_signal_score:.4f}",
        f"  Fatigue Signal Score:  {bio_prof.fatigue_signal_score:.4f}",
        f"  Instability Score:     {bio_prof.physiological_instability:.4f}",
        f"  Volatility Score:      {bio_prof.signal_volatility_score:.4f}",
        f"  Anomaly Risk Score:    {bio_prof.anomaly_risk_score:.4f}",
        f"  Biosignal Confidence:  {bio_prof.biosignal_confidence:.4f}",
        "",
        "EARLY WARNING STATUS:",
        f"  {bio_prof.early_warning_status}",
        f"  {bio_prof.stress_level_description}",
        "",
        "GLOBAL SIGNAL STATISTICS:",
    ]
    for k, v in bio_prof.global_stats.items():
        lines.append(f"  {k}: {v:.4f}")

    lines += [
        "",
        "LIMITATIONS:",
        "  These scores are derived from wearable sensor data.",
        "  They do not constitute medical or clinical diagnoses.",
        "  Individual variation, device placement, and movement",
        "  artifacts may affect signal quality and score accuracy.",
        "  Consult a qualified medical professional for any clinical",
        "  interpretation of physiological data.",
        "",
        "=" * 60,
        "Generated by Adaptive Workforce Intelligence Engine v2.1",
    ]

    report_text = "\n".join(lines)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Download Biosignal Report (TXT)",
            data=report_text.encode("utf-8"),
            file_name=f"biosignal_{bio_prof.signal_type.lower()}_report.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col2:
        csv_data = _build_csv_export()
        if csv_data:
            st.download_button(
                "📥 Download Window Features (CSV)",
                data=csv_data,
                file_name=f"biosignal_{bio_prof.signal_type.lower()}_windows.csv",
                mime="text/csv",
                use_container_width=True,
            )


def _export_hr_report():
    import datetime as _dt
    org_risk    = st.session_state.get("org_risk")
    dept_risks  = st.session_state.get("dept_risks") or []
    insight_rep = st.session_state.get("insight_report")
    exec_rep    = st.session_state.get("exec_report")
    ucr         = st.session_state.get("unified_confidence")
    contract    = _contract()
    currency    = st.session_state.get("currency", DEFAULT_CURRENCY)
    currency_sym = CURRENCY_SYMBOLS.get(currency, currency)
    now_str     = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "=" * 72,
        f"  {PLATFORM_NAME}",
        f"  WORKFORCE INTELLIGENCE REPORT  (v{REPORT_VERSION})",
        f"  Generated: {now_str}",
        f"  Currency: {currency_sym}",
        "=" * 72,
        "",
        "IMPORTANT NOTICE",
        "-" * 40,
        "  " + HUMAN_OVERSIGHT_DISCLAIMER,
        "",
    ]

    if ucr:
        lines += [
            "AI RELIABILITY & GOVERNANCE SUMMARY",
            "-" * 40,
            f"  Data Quality:       {ucr.data_quality.band} ({ucr.data_quality.score:.0%})",
            f"  Routing Confidence: {ucr.routing_confidence.band} ({ucr.routing_confidence.score:.0%})",
            f"  Model Reliability:  {ucr.model_reliability.band} ({ucr.model_reliability.score:.0%})",
            f"  Analysis Confidence:{ucr.analysis_confidence.band} ({ucr.analysis_confidence.score:.0%})",
            f"  Leakage Risk:       {ucr.leakage_risk_score:.0%}",
            f"  Executive Readiness:{ucr.executive_readiness}",
            "",
        ]

    if org_risk:
        row_lbl = "Records"
        if contract:
            row_lbl = contract.row_label().title()
        lines += [
            "WORKFORCE RISK SUMMARY",
            "-" * 40,
            f"  Total {row_lbl}:       {org_risk.total_employees:,}",
            f"  Predicted Attrition Rate: {org_risk.overall_attrition_risk:.1%}",
            f"  Priority Review Segment:  {org_risk.high_risk_employees:,} records "
            f"(flagged for HR review, not automated action)",
            f"  Sustainability Score:      {org_risk.sustainability_score:.0f}/100",
            f"  Estimated Exposure:        {currency_sym} {org_risk.total_financial_exposure:,.0f}",
            f"  Early Warning Level:       {org_risk.early_warning_level}",
            "",
        ]

    if dept_risks:
        lines.append("DEPARTMENT-LEVEL ANALYSIS")
        lines.append("-" * 40)
        for d in dept_risks:
            small = " [Small sample — interpret cautiously]" if d.n_employees < 5 else ""
            lines.append(
                f"  {d.department}: {d.n_employees} records, "
                f"avg predicted risk {d.avg_attrition_prob:.1%}, "
                f"exposure {currency_sym} {d.total_financial_exposure:,.0f}{small}"
            )
        lines.append("")
    elif org_risk and not org_risk.department_column_found:
        lines += [
            "DEPARTMENT-LEVEL ANALYSIS",
            "-" * 40,
            "  Department-level analysis unavailable — no department column detected.",
            "",
        ]

    if insight_rep:
        lines += [
            "EXECUTIVE SUMMARY",
            "-" * 40,
            "  " + insight_rep.executive_summary,
            "",
            "KEY INSIGHTS",
            "-" * 40,
        ]
        for ins in insight_rep.insights[:5]:
            lines.append(f"  [{ins.category.upper()}] {ins.title}")
            lines.append(f"    {ins.body[:140]}")
        lines.append("")

        if insight_rep.recommended_actions_30d:
            lines.append("30-DAY HR REVIEW PLAN")
            lines.append("-" * 40)
            for a in insight_rep.recommended_actions_30d:
                lines.append(f"  - {a}")
            lines.append("")

    lines += [
        "LIMITATIONS",
        "-" * 40,
        "  - Predictions are probabilistic estimates, not certainties.",
        "  - Results are dataset-specific and may not generalise.",
        "  - Human judgment is required before any workforce action.",
        "  - This report must not be used for automated personnel decisions.",
        "",
        "=" * 72,
        f"  {PLATFORM_NAME} v{PLATFORM_VERSION}  |  Report v{REPORT_VERSION}",
        "=" * 72,
    ]

    report_text = "\n".join(lines)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download Report (TXT)",
            data=report_text.encode("utf-8"),
            file_name=f"workforce_intelligence_report_{currency}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col2:
        # HTML report from ReportGenerator if available
        if exec_rep and hasattr(exec_rep, "html_text") and exec_rep.html_text:
            st.download_button(
                "Download Report (HTML)",
                data=exec_rep.html_text.encode("utf-8"),
                file_name="workforce_intelligence_report.html",
                mime="text/html",
                use_container_width=True,
            )
        else:
            st.caption("HTML report: run analysis to generate.")
    with col3:
        csv_data = _build_csv_export()
        if csv_data:
            st.download_button(
                "Download Engineered Data (CSV)",
                data=csv_data,
                file_name="hr_features.csv",
                mime="text/csv",
                use_container_width=True,
            )


def _export_survey_report():
    insight_rep = st.session_state.get("insight_report")
    contract    = _contract()

    lines = [
        "=" * 60,
        "PSYCHOLOGICAL RISK SURVEY REPORT",
        f"Dataset Type: {contract.dataset_type.replace('_', ' ').title() if contract else 'Survey'}",
        "=" * 60,
        "",
    ]

    if insight_rep:
        lines += ["EXECUTIVE SUMMARY:", insight_rep.executive_summary, ""]

    lines += [
        "=" * 60,
        "Generated by Adaptive Workforce Intelligence Engine v2.1",
    ]

    st.download_button(
        "📥 Download Survey Report (TXT)",
        data="\n".join(lines).encode("utf-8"),
        file_name="psychological_risk_report.txt",
        mime="text/plain",
        use_container_width=True,
    )


def _export_profiling_report():
    prof     = st.session_state.get("profile")
    contract = _contract()

    lines = [
        "=" * 60,
        "DATASET PROFILING REPORT",
        f"Dataset Type: {contract.dataset_type.replace('_', ' ').title() if contract else 'Unknown'}",
        "=" * 60,
        "",
    ]

    if prof:
        lines += [
            f"Rows:          {prof.n_rows:,}",
            f"Columns:       {prof.n_cols}",
            f"Quality Score: {prof.overall_quality_score:.0f}/100",
            f"File Size:     {prof.file_size_mb:.2f} MB",
            "",
            "COLUMN SUMMARY:",
        ]
        for col, cp in list(prof.columns.items())[:20]:
            lines.append(f"  {col}: {cp.inferred_type}, {cp.missing_rate:.0%} missing, {cp.n_unique} unique")

    lines += [
        "",
        "=" * 60,
        "Generated by Adaptive Workforce Intelligence Engine v2.1",
    ]

    st.download_button(
        "📥 Download Profiling Report (TXT)",
        data="\n".join(lines).encode("utf-8"),
        file_name="dataset_profiling_report.txt",
        mime="text/plain",
        use_container_width=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1: Adaptive Dataset Intelligence
# ─────────────────────────────────────────────────────────────────────────────

def page_adaptive():
    st.title("🧠 Adaptive Dataset Intelligence")
    st.caption("Universal routing engine — detects any dataset type and enforces scientifically valid analysis")

    df       = st.session_state.get("df")
    prof     = st.session_state.get("profile")
    contract = _contract()

    if df is None:
        st.info("Upload a dataset using the sidebar to begin.")
        _show_supported_types()
        return

    _render_contract_banner(contract)

    for w in (contract.warning_messages or []):
        st.warning(w)

    # Dataset-aware metric cards — NEVER "employees" for biosignal
    _adaptive_metric_card(
        contract, prof.n_rows, prof.n_cols,
        contract.quality_score, contract.target_column,
    )

    if contract.quality_issues:
        with st.expander("⚠️ Quality Issues"):
            for issue in contract.quality_issues:
                st.warning(issue)

    # Biosignal notice
    if contract.is_biosignal:
        st.markdown(
            f"""<div style="background:#d1fae5;border-left:6px solid #065f46;
            padding:1rem 1.5rem;border-radius:8px;margin:1rem 0">
            <h4 style="color:#065f46;margin:0">⚡ Biosignal Dataset Detected</h4>
            <p style="margin:0.5rem 0 0 0;color:#1e3a2f">
            Signal type: <b>{contract.detected_signal_type or 'Physiological Signal'}</b> ·
            Row unit: <b>{contract.row_label()}</b><br>
            <b>These are sensor measurements — NOT employee records.</b><br>
            Attrition prediction, HR metrics, replacement cost, department stability,
            and all employee analytics are BLOCKED for this dataset.
            Navigate to <b>Biosignal Intelligence</b> after running analysis.
            </p></div>""",
            unsafe_allow_html=True,
        )

    st.divider()
    tab_compat, tab_map, tab_sandbox, tab_run, tab_export = st.tabs([
        "📋 Compatibility Matrix", "🗺️ Column Mapping", "🛡️ Sandbox Intelligence", "🚀 Run Analysis", "📄 Export Report",
    ])

    with tab_compat:
        st.subheader("Analysis Compatibility Matrix")
        st.caption("Every analysis checked against the DatasetContract — no exceptions")
        rows = []
        for entry in contract.compatibility_matrix:
            rows.append({
                "Analysis":  entry.label,
                "Available": "✅ Yes" if entry.available else "❌ No",
                "Reason":    entry.reason,
            })
        mdf = pd.DataFrame(rows)

        def _style_row(row):
            color = "#f0fdf4" if "Yes" in row["Available"] else "#fef2f2"
            return [f"background-color: {color}"] * len(row)

        safe_styled_dataframe(mdf, _style_row, use_container_width=True, hide_index=True)

    with tab_map:
        st.subheader("Semantic Column Mapping")
        sem_map = st.session_state.get("sem_map")
        if sem_map:
            rows = [{
                "Column": col,
                "Semantic Category": m.semantic_category,
                "Confidence": f"{m.confidence:.0%}",
                "Method": m.method,
            } for col, m in sem_map.mappings.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Phase 3 semantic map
        sm_v2 = contract.semantic_map_v2
        if sm_v2:
            st.subheader("Phase 3 — Schema Intelligence")
            c1, c2, c3 = st.columns(3)
            c1.metric("Schema Coherence", f"{sm_v2.schema_coherence:.0%}")
            c2.metric("Target Candidates", len(sm_v2.target_candidates))
            c3.metric("Protected Attributes", len(sm_v2.protected_attributes))

            if sm_v2.target_candidates:
                st.success(f"Target candidates detected: **{', '.join(sm_v2.target_candidates)}**")
            if sm_v2.protected_attributes:
                st.warning(f"Protected attributes: **{', '.join(sm_v2.protected_attributes)}** — fairness audit recommended")
            if sm_v2.biosignal_columns:
                st.info(f"Biosignal columns: **{', '.join(sm_v2.biosignal_columns)}**")

            with st.expander("All Column Roles (Phase 3)"):
                _cols_dict = getattr(sm_v2, "columns", None) or {}
                role_rows = [
                    {
                        "Column": col,
                        "Role": cm.role.value if hasattr(cm.role, "value") else str(cm.role),
                        "Confidence": f"{cm.confidence:.0%}",
                        "Evidence": "; ".join(cm.evidence[:2]) if cm.evidence else "",
                    }
                    for col, cm in _cols_dict.items()
                ]
                if role_rows:
                    st.dataframe(pd.DataFrame(role_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("No column role data available.")

        st.info(f"**Pipeline**: {contract.recommended_pipeline}  \n{contract.reason[:200]}")

    with tab_sandbox:
        st.subheader("Sandbox Validation Report")
        st.caption("Pre-render gate: every analysis validated before any dashboard renders")

        rc = contract.routing_confidence
        sb = contract.sandbox_report

        if rc:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Routing Confidence", f"{rc.overall_confidence:.0%}")
            c2.metric("Confidence Band", rc.confidence_band)
            c3.metric("Routing Locked", "Yes" if rc.routing_locked else "No")
            c4.metric("Suppressed Analyses", len(rc.suppressed_analyses))
            if rc.routing_locked:
                st.success("Routing locked by hard filename rule — maximum confidence enforced.")
            if rc.suppressed_analyses:
                st.warning(f"Suppressed by low confidence: **{', '.join(rc.suppressed_analyses)}**")

        if sb:
            st.divider()
            health_pct = int(sb.dataset_health_score * 100)
            col_h, col_a, col_b = st.columns(3)
            col_h.metric("Dataset Health Score", f"{health_pct}%")
            col_a.metric("Analyses Available", len(sb.globally_available))
            col_b.metric("Analyses Blocked", len(sb.globally_blocked))

            if sb.critical_failures:
                st.error(f"Critical failures: {', '.join(sb.critical_failures)}")
            if sb.advisory_notes:
                for note in sb.advisory_notes[:3]:
                    st.info(note)

            st.markdown("**Available Analyses:**")
            avail_cols = st.columns(min(len(sb.globally_available), 4) or 1)
            for i, key in enumerate(sb.globally_available):
                avail_cols[i % len(avail_cols)].success(key.replace("_", " ").title())

            if sb.globally_blocked:
                st.markdown("**Blocked Analyses:**")
                blk_cols = st.columns(min(len(sb.globally_blocked), 4))
                for i, key in enumerate(sb.globally_blocked):
                    blk_cols[i % len(blk_cols)].error(key.replace("_", " ").title())

            with st.expander("Detailed Guard Results"):
                for analysis_key, guard_result in sb.validated_analyses.items():
                    status = "ALLOWED" if guard_result.allowed else "BLOCKED"
                    icon = "✅" if guard_result.allowed else "❌"
                    st.markdown(f"{icon} **{analysis_key}** — {status}")
                    if guard_result.violations:
                        for v in guard_result.violations:
                            st.caption(f"   Violation: {v.message}")
                    if guard_result.warnings:
                        for w in guard_result.warnings:
                            st.caption(f"   Warning: {w.message}")
        else:
            st.info("Phase 3 sandbox results not yet available for this dataset.")

    with tab_run:
        st.subheader("Run Adaptive Analysis")
        if contract.is_biosignal:
            st.info(
                "Biosignal pipeline will run on your physiological signal data.  \n"
                "Results will appear in **Biosignal Intelligence** after completion."
            )
            target_override = None
        else:
            options = ["(auto-detect)"] + list(df.columns)
            sel = st.selectbox("Target column (optional override)", options)
            target_override = None if sel == "(auto-detect)" else sel

        if st.button("🚀 Run Adaptive Analysis", type="primary", use_container_width=True):
            _run_analysis(target_override)
            if st.session_state.get("analysis_done"):
                st.success("✅ Analysis complete!")
                if contract.is_biosignal:
                    st.info("→ Navigate to **Biosignal Intelligence** to view results.")
                else:
                    st.info("→ Navigate to HR Attrition, Insights, or other pages to explore results.")

    with tab_export:
        _render_pdf_section()


def _render_contract_banner(contract: DatasetContract):
    colors = {
        "hr_attrition":         ("#1e40af", "#dbeafe"),
        "hr_workforce":         ("#1e3a5f", "#cfe2ff"),
        "biosignal_timeseries": ("#065f46", "#d1fae5"),
        "psychological_survey": ("#7c3aed", "#ede9fe"),
        "burnout_survey":       ("#9d174d", "#fce7f3"),
        "generic_timeseries":   ("#92400e", "#fef3c7"),
        "mixed_enterprise":     ("#be185d", "#fce7f3"),
        "unknown":              ("#374151", "#f3f4f6"),
    }
    bg, fg = colors.get(contract.dataset_type, ("#374151", "#f3f4f6"))
    st.markdown(
        f"""<div style="background:{fg};border-left:6px solid {bg};padding:1rem 1.5rem;
        border-radius:8px;margin-bottom:1rem">
        <h3 style="color:{bg};margin:0">
            {contract.dataset_type.replace('_', ' ').title()}
        </h3>
        <p style="margin:0.5rem 0 0 0;color:#374151">
        Confidence: <b>{contract.confidence:.0%}</b> ·
        Pipeline: <b>{contract.recommended_pipeline}</b> ·
        Row unit: <b>{contract.row_label()}</b> ·
        Subtype: <b>{contract.dataset_subtype}</b>
        </p></div>""",
        unsafe_allow_html=True,
    )


def _show_supported_types():
    st.markdown("### Supported Dataset Types")
    types = [
        ("HR Attrition", "Employee turnover prediction — supervised ML + risk scoring"),
        ("Psychological Survey", "Burnout / engagement construct estimation"),
        ("Biosignal / WESAD", "HR.csv, EDA.csv, BVP.csv — physiological signal analysis"),
        ("Generic Time-Series", "Trend detection, anomaly scoring, forecasting"),
        ("Generic Tabular", "AutoML for any structured dataset"),
        ("Unknown", "Data quality report + field mapping recommendations"),
    ]
    cols = st.columns(3)
    for i, (title, desc) in enumerate(types):
        with cols[i % 3]:
            st.markdown(f"**{title}**\n\n{desc}")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2: HR Attrition Analytics
# ─────────────────────────────────────────────────────────────────────────────

def page_hr_attrition():
    if _MODULAR:
        _hr_attrition_mod.render()
        return
    st.title("📊 HR Attrition Analytics")
    if not _guard("attrition_prediction", "HR Attrition Analytics"):
        return
    if not _require_analysis():
        return

    contract  = _contract()
    org_risk  = st.session_state.get("org_risk")
    ind_risks = st.session_state.get("ind_risks", [])
    ml_res    = st.session_state.get("ml_result")

    if org_risk is None:
        st.warning("No risk data available — re-run analysis.")
        return

    # ── KPIs — contract.row_label() guarantees no employee language for biosignal ──
    # (This page is only reachable if attrition_prediction is allowed, so is_hr = True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Total {contract.row_label().title()}", f"{org_risk.total_employees:,}")
    c2.metric("Overall Attrition Risk", f"{org_risk.overall_attrition_risk:.1%}")
    c3.metric(f"High-Risk {contract.row_label().title()}", f"{org_risk.high_risk_employees:,}")
    c4.metric("Early Warning", org_risk.early_warning_level)

    _curr      = st.session_state.get("currency", DEFAULT_CURRENCY)
    _curr_sym  = CURRENCY_SYMBOLS.get(_curr, _curr)
    c5, c6 = st.columns(2)
    c5.metric(f"Estimated Exposure ({_curr_sym})", f"{_curr_sym} {org_risk.total_financial_exposure:,.0f}")
    c6.metric("Sustainability Score", f"{org_risk.sustainability_score:.0f}/100")

    st.divider()
    _render_unified_confidence_panel()
    st.divider()

    # Attrition probability distribution — safe_render_attrition wraps it
    def _attrition_dist():
        if not ind_risks:
            return
        probs = [r.attrition_probability for r in ind_risks]
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

    safe_render_attrition(_attrition_dist)

    # Model performance table
    if ml_res and ml_res.models:
        st.subheader("Model Performance")
        rows = []
        for name, mr in ml_res.models.items():
            row = {"Model": f"⭐ {name}" if name == ml_res.best_model_name else name}
            row.update(mr.metrics)
            row["Train (s)"] = mr.train_time_s
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Top risk table — safe_render_employee_metrics ensures not shown for biosignal
    def _top_risk_table():
        if not ind_risks:
            return
        st.subheader(f"Top 20 Highest-Risk {contract.row_label().title()} — Flagged for HR Review")
        st.caption(
            "Identifiers are masked by default. This list is for HR review purposes only — "
            "no automated action should be taken based solely on these scores."
        )
        _mask = st.session_state.get("mask_employee_ids", True)
        sorted_r = sorted(ind_risks, key=lambda r: r.attrition_probability, reverse=True)[:20]
        tbl = pd.DataFrame([{
            "ID":                f"Employee #{i+1:03d}" if _mask else str(r.employee_idx),
            "Predicted Risk":    f"{r.attrition_probability:.1%}",
            "Risk Level":        r.risk_level,
            "Burnout Indicator": "N/A" if r.burnout_risk is None else f"{r.burnout_risk:.1%}",
            "Burnout Source":    getattr(r, "burnout_mode", "—"),
            f"Exposure ({_curr_sym})": f"{_curr_sym} {r.financial_exposure:,.0f}",
            "Review Status":     "Flagged for HR review" if r.risk_level in ("High", "Critical") else "Standard monitoring",
        } for i, r in enumerate(sorted_r)])
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    safe_render_employee_metrics(_top_risk_table)

    # Retention ROI
    def _retention_roi():
        st.subheader("Retention ROI Summary")
        c1, c2 = st.columns(2)
        c1.metric(f"Estimated Exposure ({_curr_sym})", f"{_curr_sym} {org_risk.total_financial_exposure:,.0f}")
        c2.metric("High-Risk Headcount", org_risk.high_risk_employees)
        st.caption(
            f"Replacement cost estimated at ~50% annual salary per attriting employee "
            f"(configurable in settings). Currency: {_curr}."
        )

    safe_render_retention_roi(_retention_roi)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3: Psychological Risk
# ─────────────────────────────────────────────────────────────────────────────

def page_psychological():
    st.title("🧬 Psychological Risk Intelligence")
    if not _guard("psychological_constructs", "Psychological Risk Intelligence"):
        return
    if not _require_analysis():
        return

    df_eng = st.session_state.get("df_eng")
    if df_eng is None:
        st.warning("No data available.")
        return

    constructs = [c for c in [
        "BurnoutRiskComposite", "SatisfactionIndex", "EngagementScore",
        "RetentionRisk", "ManagerialSupportIndex", "EmployeeStabilityRisk",
        "CompensationEquity", "WorkLifeBalanceRisk", "CareerProgressionScore",
        "PsychologicalWellbeingScore",
    ] if c in df_eng.columns]

    if not constructs:
        st.info("No psychological constructs were estimated for this dataset.")
        return

    means = {c: float(df_eng[c].mean()) for c in constructs}
    fig = go.Figure(go.Bar(
        x=list(means.values()), y=list(means.keys()),
        orientation="h",
        marker_color=["#dc2626" if v > 0.65 else "#3b82f6" for v in means.values()],
    ))
    fig.update_layout(title="Mean Construct Scores (0–1)", xaxis_title="Score", height=420)
    st.plotly_chart(fig, use_container_width=True)

    if len(constructs) >= 3:
        corr = df_eng[constructs].corr()
        fig2 = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                         title="Construct Correlation Matrix")
        st.plotly_chart(fig2, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 4: Biosignal Intelligence — FULL DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

def page_biosignal():
    st.title("⚡ Biosignal Intelligence")
    st.caption("Physiological signal analysis — wearable sensor data only (non-clinical)")

    contract = _contract()

    if contract is None:
        st.info("Upload a biosignal file (HR.csv, EDA.csv, BVP.csv, TEMP.csv, ACC.csv, IBI.csv) to begin.")
        _show_biosignal_info()
        return

    if not contract.is_biosignal:
        st.warning(
            f"The loaded dataset is classified as "
            f"**{contract.dataset_type.replace('_', ' ').title()}**, not as a biosignal file.  \n"
            "Upload HR.csv, EDA.csv, BVP.csv, TEMP.csv, ACC.csv, or IBI.csv for physiological analysis."
        )
        return

    if not st.session_state.get("analysis_done"):
        st.info("Run analysis from the **Adaptive Dataset Intelligence** page first.")
        return

    bio_prof: Optional[BiosignalProfile] = st.session_state.get("biosignal_profile")
    if bio_prof is None:
        st.error("No biosignal profile available. Re-run analysis from Page 1.")
        return

    # ── 1. Non-clinical disclaimer — ALWAYS FIRST ─────────────────────────────
    st.markdown(
        f"""<div style="background:#fef9c3;border-left:6px solid #ca8a04;
        padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
        <b style="color:#854d0e">⚕️ Non-Clinical Disclaimer</b><br>
        <span style="color:#713f12;font-size:0.9rem">
        {bio_prof.disclaimer}
        </span></div>""",
        unsafe_allow_html=True,
    )

    # ── 2. Signal Overview ─────────────────────────────────────────────────────
    st.markdown(f"## {bio_prof.canonical_name} — Signal Overview")

    sig_desc = {
        "HR":   "Heart Rate (HR) measures beats per minute derived from photoplethysmography or ECG.",
        "EDA":  "Electrodermal Activity (EDA) measures skin conductance — a proxy for sympathetic nervous system arousal.",
        "BVP":  "Blood Volume Pulse (BVP) measures the volumetric change in blood in peripheral tissues.",
        "TEMP": "Skin Temperature (TEMP) reflects peripheral blood flow and thermoregulatory responses.",
        "ACC":  "Accelerometer (ACC) data reflects body movement intensity and activity levels.",
        "IBI":  "Inter-Beat Interval (IBI) measures the time between successive heartbeats, used to derive HRV.",
    }.get(bio_prof.signal_type, f"Physiological signal: {bio_prof.canonical_name}")

    st.info(f"**Signal description:** {sig_desc}")

    # ── 3. Primary metric cards — dataset-aware labels ─────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Signal Samples Analysed",        # NOT "Employees Analysed"
        f"{bio_prof.n_samples:,}",
        help="Total physiological signal measurements in this recording",
    )
    c2.metric(
        "Windows Analysed",
        f"{bio_prof.n_windows:,}",
        help="30-second analysis windows with 50% overlap",
    )
    c3.metric(
        "Recording Duration",
        f"{bio_prof.duration_seconds:.0f}s" if bio_prof.duration_seconds > 0 else "N/A",
        help="Total duration of the physiological recording",
    )
    c4.metric(
        "Sampling Frequency",
        f"{bio_prof.estimated_fs:.1f} Hz" if bio_prof.estimated_fs > 0 else "Unknown",
        help="Estimated signal sampling rate",
    )

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Signal Quality", f"{bio_prof.quality_score:.0f}/100")
    c6.metric("Missing Rate", f"{bio_prof.missing_rate:.1%}")
    c7.metric("Anomaly Count", bio_prof.anomaly_count)
    c8.metric("Biosignal Confidence", f"{bio_prof.biosignal_confidence:.0%}")

    # ── 4. Physiological Stress Proxy Banner ──────────────────────────────────
    stress_colors = {
        "Low":      ("#16a34a", "#f0fdf4"),
        "Moderate": ("#d97706", "#fffbeb"),
        "Elevated": ("#ea580c", "#fff7ed"),
        "Critical": ("#dc2626", "#fef2f2"),
    }
    sc, bg = stress_colors.get(bio_prof.stress_level_label, ("#374151", "#f9fafb"))
    st.markdown(
        f"""<div style="background:{bg};border-left:6px solid {sc};
        padding:1.2rem 1.5rem;border-radius:8px;margin:1rem 0">
        <h3 style="color:{sc};margin:0">
            Physiological Stress Proxy: <b>{bio_prof.stress_level_label}</b>
        </h3>
        <p style="margin:0.5rem 0 0.2rem 0;color:#374151">
            {bio_prof.stress_level_description}
        </p>
        <p style="margin:0;color:#6b7280;font-size:0.85rem">
            Stress signal score: <b>{bio_prof.stress_signal_score:.4f}</b> ·
            Fatigue proxy: <b>{bio_prof.fatigue_signal_score:.4f}</b> ·
            Physiological instability: <b>{bio_prof.physiological_instability:.4f}</b>
        </p></div>""",
        unsafe_allow_html=True,
    )

    # ── 5. Early Warning Status ────────────────────────────────────────────────
    ew_colors = {
        "Normal":   ("#16a34a", "#f0fdf4"),
        "Watch":    ("#d97706", "#fffbeb"),
        "Warning":  ("#ea580c", "#fff7ed"),
        "Critical": ("#dc2626", "#fef2f2"),
    }
    ew_level = bio_prof.early_warning_status
    ewc, ewbg = ew_colors.get(ew_level, ("#374151", "#f9fafb"))
    st.markdown(
        f"""<div style="background:{ewbg};border-left:5px solid {ewc};
        padding:0.8rem 1.2rem;border-radius:6px;margin:0.5rem 0">
        <b style="color:{ewc}">Early Warning Status: {ew_level}</b>
        </div>""",
        unsafe_allow_html=True,
    )

    # Warnings
    for w in (bio_prof.warnings or []):
        st.warning(w)

    st.divider()

    # ── 6. Dashboard Tabs ──────────────────────────────────────────────────────
    tab_stats, tab_vol, tab_anomaly, tab_quality, tab_windows, tab_scores, tab_ts, tab_interp = st.tabs([
        "📊 Signal Statistics",
        "📉 Volatility Analysis",
        "🚨 Anomaly Detection",
        "🔬 Signal Quality",
        "🔲 Window Analysis",
        "🧮 Composite Scores",
        "📈 Trend Analysis",
        "📖 Interpretation & Limits",
    ])

    # ── Tab 1: Signal Statistics ───────────────────────────────────────────────
    with tab_stats:
        st.subheader("Global Signal Statistics")
        col_l, col_r = st.columns(2)
        with col_l:
            stats_df = pd.DataFrame(
                [(k, round(v, 4)) for k, v in bio_prof.global_stats.items()],
                columns=["Statistic", "Value"],
            )
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
        with col_r:
            show = {k: v for k, v in bio_prof.global_stats.items()
                    if k in ("mean", "std", "median", "range", "iqr")}
            if show:
                fig = px.bar(
                    x=list(show.keys()), y=list(show.values()),
                    title="Key Signal Statistics",
                    color_discrete_sequence=["#3b82f6"],
                )
                st.plotly_chart(fig, use_container_width=True)

        # Distribution of raw signal values
        wf = bio_prof.window_features_df
        if wf is not None and "Mean" in wf.columns:
            fig2 = px.histogram(
                wf, x="Mean", nbins=30,
                title=f"Distribution of Window Mean {bio_prof.canonical_name} Values",
                color_discrete_sequence=["#0ea5e9"],
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── Tab 2: Volatility Analysis ─────────────────────────────────────────────
    with tab_vol:
        st.subheader("Signal Volatility Analysis")
        wf = bio_prof.window_features_df

        col1, col2 = st.columns(2)
        col1.metric("Signal Volatility Score", f"{bio_prof.signal_volatility_score:.4f}",
                    help="Overall measure of signal variability across windows (0=stable, 1=highly volatile)")
        col2.metric("Physiological Instability", f"{bio_prof.physiological_instability:.4f}",
                    help="Combined index of signal instability patterns")

        if wf is not None:
            vol_cols = [c for c in ["Volatility", "Std", "SignalVolatilityScore"] if c in wf.columns]
            if vol_cols:
                fig = px.line(
                    wf, x="WindowID", y=vol_cols[0],
                    title=f"{vol_cols[0]} Over Time Windows",
                    color_discrete_sequence=["#f59e0b"],
                )
                fig.add_hline(
                    y=float(wf[vol_cols[0]].mean()),
                    line_dash="dash", line_color="gray",
                    annotation_text="Mean",
                )
                st.plotly_chart(fig, use_container_width=True)

            if "Std" in wf.columns and "Mean" in wf.columns:
                fig2 = px.scatter(
                    wf, x="Mean", y="Std",
                    title="Signal Mean vs Standard Deviation (Window-Level)",
                    color="SignalVolatilityScore" if "SignalVolatilityScore" in wf.columns else None,
                    color_continuous_scale="Oranges",
                )
                st.plotly_chart(fig2, use_container_width=True)

        st.caption(
            "Volatility reflects natural physiological variation. "
            "High volatility may indicate stress responses, movement artifacts, or signal quality issues."
        )

    # ── Tab 3: Anomaly Detection ───────────────────────────────────────────────
    with tab_anomaly:
        st.subheader("Anomaly Detection")

        col1, col2 = st.columns(2)
        col1.metric("Total Anomaly Count", bio_prof.anomaly_count,
                    help="Windows with signal values exceeding 2.5 standard deviations from mean")
        col2.metric("Anomaly Risk Score", f"{bio_prof.anomaly_risk_score:.4f}",
                    help="Proportion of windows flagged as anomalous (0=none, 1=all)")

        wf = bio_prof.window_features_df
        if wf is not None and "AnomalyRiskScore" in wf.columns:
            fig = px.line(
                wf, x="WindowID", y="AnomalyRiskScore",
                title="Anomaly Risk Score Over Time Windows",
                color_discrete_sequence=["#ef4444"],
            )
            threshold_line = 0.5
            fig.add_hline(y=threshold_line, line_dash="dash", line_color="#dc2626",
                          annotation_text="Anomaly Threshold")
            st.plotly_chart(fig, use_container_width=True)

            # Anomaly windows table
            anomaly_windows = wf[wf["AnomalyRiskScore"] > threshold_line]
            if len(anomaly_windows) > 0:
                st.subheader(f"Flagged Anomaly Windows ({len(anomaly_windows)})")
                show_cols = [c for c in ["WindowID", "SampleStart", "SampleEnd", "Mean",
                                         "Std", "AnomalyRiskScore", "SignalQuality"]
                             if c in wf.columns]
                st.dataframe(
                    anomaly_windows[show_cols].sort_values("AnomalyRiskScore", ascending=False),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.success("No anomaly windows detected above threshold.")
        else:
            st.info("Anomaly window data not available for this signal.")

        st.caption(
            "Anomaly windows may reflect genuine physiological events, "
            "sensor artifacts, or participant movement. "
            "Clinical interpretation requires domain expertise."
        )

    # ── Tab 4: Signal Quality ──────────────────────────────────────────────────
    with tab_quality:
        st.subheader("Signal Quality Assessment")

        quality_colors = {
            (0, 40):  ("#dc2626", "#fef2f2", "Poor"),
            (40, 60): ("#d97706", "#fffbeb", "Fair"),
            (60, 80): ("#2563eb", "#eff6ff", "Good"),
            (80, 101):("#16a34a", "#f0fdf4", "Excellent"),
        }
        q = bio_prof.quality_score
        qc, qbg, qlabel = "#374151", "#f9fafb", "Unknown"
        for (lo, hi), (color, bg, label) in quality_colors.items():
            if lo <= q < hi:
                qc, qbg, qlabel = color, bg, label

        st.markdown(
            f"""<div style="background:{qbg};border-left:6px solid {qc};
            padding:1rem 1.5rem;border-radius:8px">
            <h3 style="color:{qc};margin:0">Signal Quality: {qlabel} ({q:.0f}/100)</h3>
            <p style="margin:0.5rem 0 0 0;color:{qc}">
            Missing rate: <b>{bio_prof.missing_rate:.1%}</b> ·
            Anomaly count: <b>{bio_prof.anomaly_count}</b>
            </p></div>""",
            unsafe_allow_html=True,
        )

        wf = bio_prof.window_features_df
        if wf is not None and "SignalQuality" in wf.columns:
            fig = px.histogram(
                wf, x="SignalQuality", nbins=20,
                title="Distribution of Window-Level Signal Quality",
                color_discrete_sequence=["#22c55e"],
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Quality Factors")
        quality_items = [
            ("Missing Data", f"{bio_prof.missing_rate:.1%}", bio_prof.missing_rate < 0.05),
            ("Anomaly Rate", f"{bio_prof.anomaly_count} windows", bio_prof.anomaly_count < 10),
            ("Signal Confidence", f"{bio_prof.biosignal_confidence:.0%}", bio_prof.biosignal_confidence > 0.6),
        ]
        for label, value, ok in quality_items:
            icon = "✅" if ok else "⚠️"
            st.markdown(f"{icon} **{label}**: {value}")

    # ── Tab 5: Window Analysis ─────────────────────────────────────────────────
    with tab_windows:
        wf = bio_prof.window_features_df
        if wf is None or len(wf) == 0:
            st.warning("No windows generated — signal may be too short (minimum ~60 samples required).")
        else:
            st.caption(
                f"**{len(wf):,} time windows** · 30-second windows with 50% overlap · "
                f"Row unit: {contract.row_label()} (NOT employees)"
            )

            plot_cols = [c for c in [
                "Mean", "Std", "Volatility",
                "StressSignalScore", "FatigueSignalScore",
                "PhysiologicalInstability", "SignalVolatilityScore",
                "AnomalyRiskScore",
            ] if c in wf.columns]

            sel_col = st.selectbox("Plot metric over time:", plot_cols or ["Mean"])
            if sel_col in wf.columns:
                fig = px.line(
                    wf, x="WindowID", y=sel_col,
                    title=f"{sel_col} over Time Windows",
                    color_discrete_sequence=["#3b82f6"],
                )
                st.plotly_chart(fig, use_container_width=True)

            if "StressSignalScore" in wf.columns:
                st.subheader(f"Top 10 Highest-Stress Windows")
                top_w = wf.nlargest(10, "StressSignalScore")[
                    [c for c in ["WindowID", "SampleStart", "SampleEnd", "Mean",
                                 "Std", "StressSignalScore", "AnomalyRiskScore",
                                 "SignalQuality"] if c in wf.columns]
                ]
                st.dataframe(top_w, use_container_width=True, hide_index=True)

            st.subheader("Full Window Feature Table")
            st.dataframe(wf, use_container_width=True, hide_index=True)

    # ── Tab 6: Composite Scores ────────────────────────────────────────────────
    with tab_scores:
        st.subheader("Composite Physiological Scores")
        st.caption("All scores are proxy signals (0–1 scale) — see Interpretation tab for meaning")

        score_data = {
            "Stress Signal Score":       bio_prof.stress_signal_score,
            "Fatigue Signal Score":      bio_prof.fatigue_signal_score,
            "Physiological Instability": bio_prof.physiological_instability,
            "Signal Volatility":         bio_prof.signal_volatility_score,
            "Anomaly Risk Score":        bio_prof.anomaly_risk_score,
            "Biosignal Confidence":      bio_prof.biosignal_confidence,
        }

        fig = go.Figure(go.Bar(
            x=list(score_data.values()),
            y=list(score_data.keys()),
            orientation="h",
            marker_color=[
                "#dc2626" if v >= 0.65 else "#d97706" if v >= 0.40 else "#3b82f6"
                for v in score_data.values()
            ],
            text=[f"{v:.4f}" for v in score_data.values()],
            textposition="outside",
        ))
        fig.update_layout(
            xaxis=dict(range=[0, 1], title="Score (0 = low, 1 = high)"),
            title="Composite Scores — Physiological Signal Analysis",
            height=380,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Radar chart
        labels = list(score_data.keys())
        values = list(score_data.values())
        fig2 = go.Figure(go.Scatterpolar(
            r=values + [values[0]],
            theta=labels + [labels[0]],
            fill="toself",
            fillcolor="rgba(59,130,246,0.2)",
            line_color="#3b82f6",
        ))
        fig2.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            title="Score Profile — Radar View",
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Stress vs Fatigue scatter
        wf = bio_prof.window_features_df
        if wf is not None and "StressSignalScore" in wf.columns and "FatigueSignalScore" in wf.columns:
            fig3 = px.scatter(
                wf, x="StressSignalScore", y="FatigueSignalScore",
                color="PhysiologicalInstability" if "PhysiologicalInstability" in wf.columns else None,
                title="Stress Proxy vs Fatigue Proxy — Window Space",
                color_continuous_scale="Reds",
                labels={
                    "StressSignalScore":       "Stress Signal Score",
                    "FatigueSignalScore":      "Fatigue Signal Score",
                    "PhysiologicalInstability":"Instability",
                },
            )
            st.plotly_chart(fig3, use_container_width=True)

    # ── Tab 7: Trend Analysis ──────────────────────────────────────────────────
    with tab_ts:
        ts_res = st.session_state.get("ts_result")
        if ts_res and ts_res.n_periods > 0:
            st.subheader("Stress Signal Trend")
            for metric, trend in ts_res.trends.items():
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Direction",  trend.direction.title())
                c2.metric("Magnitude",  trend.magnitude.title())
                c3.metric("R²",         f"{trend.r_squared:.3f}")
                c4.metric("p-value",    f"{trend.p_value:.3f}")

            if ts_res.anomalies:
                st.subheader(f"Trend Anomalies ({len(ts_res.anomalies)})")
                adf = pd.DataFrame([{
                    "Window":   a.period,
                    "Value":    a.value,
                    "Z-Score":  a.z_score,
                    "Severity": a.severity,
                } for a in ts_res.anomalies])
                st.dataframe(adf, use_container_width=True, hide_index=True)

            if ts_res.forecasts:
                st.subheader("Stress Score Forecast")
                rows = [{
                    "Horizon (windows)": h,
                    "Projected":         f"{fc.projected:.4f}",
                    "Lower 95%":         f"{fc.lower_95:.4f}",
                    "Upper 95%":         f"{fc.upper_95:.4f}",
                    "Method":            fc.method,
                } for h, fc in ts_res.forecasts.items()]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info(
                "Trend analysis requires sufficient windows. "
                "Upload a longer recording for time-series decomposition."
            )

    # ── Tab 8: Interpretation & Limitations ───────────────────────────────────
    with tab_interp:
        st.subheader("Interpretation Guide")

        sig_interp = {
            "HR": """
**Heart Rate (HR) interpretation:**
- HR reflects autonomic nervous system regulation of cardiac output.
- Elevated HR proxy scores may indicate physical exertion, thermal stress, or autonomic arousal.
- HR variability (if IBI available) provides more refined stress indicators.
- Normal resting HR: 60–100 BPM; values outside this range warrant contextual interpretation.
""",
            "EDA": """
**Electrodermal Activity (EDA) interpretation:**
- EDA reflects sympathetic nervous system arousal via sweat gland activity.
- Elevated EDA activation scores may indicate emotional arousal, cognitive load, or stress responses.
- EDA is highly sensitive to movement artifacts — physical activity inflates scores.
- Tonic EDA level reflects baseline arousal; phasic responses indicate event-linked activation.
""",
            "BVP": """
**Blood Volume Pulse (BVP) interpretation:**
- BVP measures pulsatile blood flow in peripheral tissue (typically finger/wrist).
- High cardiovascular signal instability may reflect autonomic dysregulation or movement artifacts.
- BVP-derived heart rate provides similar information to ECG-derived HR at lower precision.
- Signal quality is highly sensitive to sensor placement and movement.
""",
            "TEMP": """
**Skin Temperature (TEMP) interpretation:**
- Peripheral skin temperature reflects peripheral vasoconstriction/dilation.
- Stress typically causes peripheral vasoconstriction → temperature decrease.
- Temperature changes are slow (minutes) compared to HR/EDA responses.
- Environmental temperature substantially influences readings.
""",
            "ACC": """
**Accelerometer (ACC) interpretation:**
- Accelerometer data reflects body movement intensity.
- High movement intensity confounds other physiological signals (HR, EDA, BVP).
- Movement intensity can be used to identify active vs. sedentary periods.
- Inactivity may indicate sedentary posture or sleep states.
""",
            "IBI": """
**Inter-Beat Interval (IBI) / HRV interpretation:**
- IBI is the time between consecutive heartbeats in milliseconds.
- SDNN (standard deviation of IBI) reflects overall HRV — higher = greater autonomic flexibility.
- RMSSD reflects parasympathetic activity — lower RMSSD may indicate stress or fatigue.
- HRV is one of the most validated stress biomarkers in psychophysiology research.
""",
        }

        interp_text = sig_interp.get(bio_prof.signal_type, f"**{bio_prof.canonical_name}** signal interpretation.")
        st.markdown(interp_text)

        st.divider()
        st.subheader("Limitations")
        st.markdown("""
**Known limitations of wearable biosignal analysis:**

1. **Non-clinical**: Scores derived here are physiological proxies, not clinical diagnoses.
   A physiological stress proxy score does not confirm medical stress disorder or burnout.

2. **Individual variation**: Physiological baselines vary substantially between individuals.
   Scores are relative to within-recording statistics, not population norms.

3. **Context dependence**: Physical activity, ambient temperature, caffeine, medications,
   and posture all influence physiological signals independently of psychological state.

4. **Single-sensor limitation**: Individual signals provide limited information.
   Multi-modal fusion (HR + EDA + TEMP) provides more robust stress indicators.

5. **Short recordings**: Analysis quality improves with recording duration.
   Very short recordings (<5 minutes) may not yield reliable composite scores.

6. **Movement artifacts**: Physical movement substantially contaminates HR, BVP, and EDA signals.
   High anomaly counts may reflect artifacts rather than physiological events.

7. **No employee data**: This dataset contains physiological measurements only.
   No attrition prediction, employee risk scores, or workforce analytics are applicable.
""")

        st.info(bio_prof.disclaimer)

        # Export
        st.divider()
        _export_biosignal_report()


def _show_biosignal_info():
    st.markdown("""
### Supported Biosignal Files
| File | Signal | Frequency |
|------|--------|-----------|
| `HR.csv` | Heart Rate (BPM) | 1 Hz |
| `EDA.csv` | Electrodermal Activity (μS) | 4 Hz |
| `BVP.csv` | Blood Volume Pulse | 64 Hz |
| `TEMP.csv` | Skin Temperature (°C) | 4 Hz |
| `ACC.csv` | Accelerometer (m/s²) | 32 Hz |
| `IBI.csv` | Inter-Beat Interval (s) | Variable |

Compatible with WESAD dataset format and similar wearable exports.
""")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 5: Time-Series Early Warning
# ─────────────────────────────────────────────────────────────────────────────

def page_timeseries():
    st.title("📈 Time-Series Early Warning")
    if not _guard("timeseries_forecast", "Time-Series Early Warning"):
        return
    if not _require_analysis():
        return

    ts_res = st.session_state.get("ts_result")
    if ts_res is None or ts_res.n_periods == 0:
        st.warning("No time-series data available for this dataset.")
        return

    if ts_res.synthetic_mode:
        st.info("ℹ️ Synthetic tenure-cohort timeline (no date column detected).")

    esc = ts_res.escalation
    if esc:
        esc_colors = {"Critical": "#dc2626", "Elevated": "#ea580c",
                      "Watchlist": "#d97706", "Stable": "#16a34a"}
        col = esc_colors.get(esc.level, "#374151")
        st.markdown(
            f"""<div style="background:{col}22;border-left:6px solid {col};
            padding:1rem;border-radius:8px">
            <h3 style="color:{col}">Early Warning: {esc.level} (Score: {esc.score:.0f}/100)</h3>
            <p>{esc.recommended_action}</p>
            {"".join(f"<p>• {d}</p>" for d in esc.drivers)}
            </div>""",
            unsafe_allow_html=True,
        )

    for metric, trend in ts_res.trends.items():
        st.subheader(f"Trend: {metric}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Direction", trend.direction.title())
        c2.metric("Magnitude", trend.magnitude.title())
        c3.metric("R²", f"{trend.r_squared:.3f}")
        c4.metric("p-value", f"{trend.p_value:.3f}")

    if ts_res.forecasts:
        st.subheader("Forecast with 95% Confidence Bands")
        rows = [{
            "Horizon": h,
            "Projected": f"{fc.projected:.4f}",
            "Lower 95%": f"{fc.lower_95:.4f}",
            "Upper 95%": f"{fc.upper_95:.4f}",
            "CI Width": f"{fc.band_width:.4f}",
            "Confidence": f"{fc.confidence:.0%}",
            "Method": fc.method,
        } for h, fc in ts_res.forecasts.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if ts_res.anomalies:
        st.subheader(f"Anomalies ({len(ts_res.anomalies)})")
        adf = pd.DataFrame([{
            "Period": a.period, "Metric": a.metric,
            "Value": a.value, "Z-Score": a.z_score,
            "Severity": a.severity,
        } for a in ts_res.anomalies])
        st.dataframe(adf, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 6: Department & Org Risk
# ─────────────────────────────────────────────────────────────────────────────

def page_department():
    if _MODULAR:
        _department_mod.render()
        return
    st.title("🏢 Department & Organisational Risk")
    if not _guard("department_stability", "Department & Org Risk"):
        return
    if not _require_analysis():
        return

    contract   = _contract()
    org_risk   = st.session_state.get("org_risk")
    dept_risks = st.session_state.get("dept_risks", [])

    _curr     = st.session_state.get("currency", DEFAULT_CURRENCY)
    _curr_sym = CURRENCY_SYMBOLS.get(_curr, _curr)

    # Org-level KPIs always shown if org_risk present
    if org_risk:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Total {contract.row_label().title()}", f"{org_risk.total_employees:,}")
        c2.metric("High-Risk",      f"{org_risk.high_risk_employees:,}")
        c3.metric("Sustainability", f"{org_risk.sustainability_score:.0f}/100")
        c4.metric("Early Warning",  org_risk.early_warning_level)
        st.divider()

    # Department breakdown — honest if unavailable
    dept_col_found = getattr(org_risk, "department_column_found", None) if org_risk else None

    if dept_col_found is False:
        st.info(
            "**Department-level analysis unavailable** — no department column was detected in this dataset.  \n"
            "To enable department breakdowns, ensure your dataset includes a column named "
            "'Department', 'Division', 'Business Unit', 'Team', or similar."
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
            "Department":         d.department,
            "Headcount":          d.n_employees,
            "Avg Risk":           d.avg_attrition_prob,
            "High Risk %":        d.high_risk_pct,
            f"Exposure ({_curr_sym})": f"{_curr_sym} {d.total_financial_exposure:,.0f}",
            "Reliability":        d.reliability_flag,
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

    # safe_render_department ensures this never shows for biosignal
    safe_render_department(_dept_render)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 7: Executive Insights
# ─────────────────────────────────────────────────────────────────────────────

def page_insights():
    if _MODULAR:
        _insights_mod.render()
        return
    st.title("💡 Executive Insights & Action Plan")
    if not _require_analysis():
        return

    insight_rep = st.session_state.get("insight_report")
    contract    = _contract()

    if insight_rep is None:
        st.warning("No insight report available.")
        return

    # Human oversight disclaimer — always shown
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

    colors = {"Critical": "#dc2626", "Elevated": "#ea580c",
              "Watchlist": "#d97706", "Stable": "#16a34a"}
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
        icon = {"risk": "🔴", "warning": "🟡",
                "opportunity": "🟢", "recommendation": "🔵"}.get(ins.category, "⚪")
        with st.expander(f"{icon} [{ins.category.upper()}] {ins.title}"):
            st.write(ins.body)
            if ins.action:
                st.success(f"**Suggested HR Action (requires validation):** {ins.action}")

    # 30/60/90 day plan — only for non-biosignal datasets
    if not (contract and contract.is_biosignal):
        st.divider()
        st.subheader("30 / 60 / 90-Day Action Plan")
        c30, c60, c90 = st.columns(3)
        with c30:
            st.markdown("**30-Day**")
            for a in insight_rep.recommended_actions_30d or ["None identified"]:
                st.markdown(f"• {a}")
        with c60:
            st.markdown("**60-Day**")
            for a in insight_rep.recommended_actions_60d or ["None identified"]:
                st.markdown(f"• {a}")
        with c90:
            st.markdown("**90-Day**")
            for a in insight_rep.recommended_actions_90d or ["None identified"]:
                st.markdown(f"• {a}")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 8: Model Analytics
# ─────────────────────────────────────────────────────────────────────────────

def page_model():
    st.title("⚙️ Model & AutoML Analytics")
    if not _guard("attrition_prediction", "Model Analytics"):
        return
    if not _require_analysis():
        return

    ml_res = st.session_state.get("ml_result")
    if ml_res is None:
        st.info("No supervised model was trained (unsupervised mode or no target column).")
        return

    st.subheader("Model Comparison")
    rows = []
    for name, mr in ml_res.models.items():
        row = {"Model": f"⭐ {name}" if name == ml_res.best_model_name else name}
        row.update(mr.metrics)
        row["Train (s)"] = mr.train_time_s
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.metric("Optimal Threshold (OOF F1)", f"{ml_res.optimal_threshold:.2f}")

    best = ml_res.models.get(ml_res.best_model_name)
    if best and best.feature_importances:
        st.subheader(f"Feature Importances — {ml_res.best_model_name}")
        fi  = best.feature_importances
        top = dict(list(fi.items())[:20])
        fig = px.bar(
            x=list(top.values()), y=list(top.keys()),
            orientation="h", title=f"Top {len(top)} Features",
            color=list(top.values()), color_continuous_scale="Blues",
        )
        fig.update_layout(showlegend=False, height=500)
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 9: Explainability & Governance
# ─────────────────────────────────────────────────────────────────────────────

def _confidence_badge(band: str, score: float) -> str:
    colors = {
        "High":       ("#16a34a", "#f0fdf4"),
        "Moderate":   ("#d97706", "#fffbeb"),
        "Low":        ("#ea580c", "#fff7ed"),
        "Unreliable": ("#dc2626", "#fef2f2"),
        "N/A":        ("#6b7280", "#f9fafb"),
    }
    c, bg = colors.get(band, ("#6b7280", "#f9fafb"))
    return (
        f'<span style="background:{bg};color:{c};border:1px solid {c};'
        f'border-radius:4px;padding:2px 8px;font-size:0.82rem;font-weight:700">'
        f'{band} {score:.0%}</span>'
    )


def page_explainability():
    st.title("🔍 Explainability & Governance")
    st.caption("SHAP feature importance, provenance traces, bias audits, and confidence governance")

    if not _require_analysis():
        return

    contract       = _contract()
    explain_rep    = st.session_state.get("explain_report")
    ethical_rep    = st.session_state.get("ethical_report")
    conf_prof      = st.session_state.get("confidence_profile")
    exec_report    = st.session_state.get("exec_report")
    ml_res         = st.session_state.get("ml_result")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_explain, tab_ethics, tab_conf, tab_provenance, tab_report, tab_leakage = st.tabs([
        "🧠 Explainability",
        "⚖️ Ethical Governance",
        "📊 Confidence",
        "🔗 Provenance",
        "📄 Executive Report",
        "🔬 Leakage & Validity",
    ])

    # ── Tab 1: Explainability ──────────────────────────────────────────────────
    with tab_explain:
        st.subheader("Feature Importance & Explainability")

        if explain_rep is None:
            st.info("Run analysis on an HR dataset to see explainability.")
        else:
            # Global summary
            st.markdown(
                f"""<div style="background:#eff6ff;border-left:5px solid #3b82f6;
                padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
                <b style="color:#1e40af">Explainability Summary</b><br>
                <span style="color:#1e3a8a">{explain_rep.global_summary}</span>
                </div>""",
                unsafe_allow_html=True,
            )

            if explain_rep.shap_available:
                st.success("SHAP values computed — feature attributions are model-based.")
            else:
                st.info("SHAP not available — feature importances used as proxy.")

            # Top features table
            if explain_rep.top_features:
                rows = []
                for ff in explain_rep.top_features:
                    rows.append({
                        "Feature":     ff.feature_name,
                        "Importance":  f"{ff.importance_score:.4f}",
                        "Direction":   ff.direction.replace("_", " ").title(),
                        "Magnitude":   ff.magnitude.title(),
                        "Explanation": ff.plain_english,
                        "Data Source": ff.data_source,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # Bar chart
                feat_names  = [ff.feature_name for ff in explain_rep.top_features[:12]]
                feat_scores = [ff.importance_score for ff in explain_rep.top_features[:12]]
                feat_colors = [
                    "#dc2626" if "increase" in ff.direction else
                    "#16a34a" if "decrease" in ff.direction else "#6b7280"
                    for ff in explain_rep.top_features[:12]
                ]
                fig = go.Figure(go.Bar(
                    x=feat_scores, y=feat_names, orientation="h",
                    marker_color=feat_colors,
                    text=[f"{s:.4f}" for s in feat_scores],
                    textposition="outside",
                ))
                fig.update_layout(
                    title="Top Feature Importances",
                    xaxis_title="Importance Score",
                    height=max(300, len(feat_names) * 35),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)

            # Reasoning chain
            if explain_rep.reasoning_chain:
                with st.expander("Reasoning Chain"):
                    for i, step in enumerate(explain_rep.reasoning_chain, 1):
                        st.write(f"{i}. {step}")

            if explain_rep.uncertainty_note:
                st.warning(explain_rep.uncertainty_note)

        # Feature Trustworthiness always shown if available
        st.divider()
        _render_feature_trust_panel()

    # ── Tab 2: Ethical Governance ─────────────────────────────────────────────
    with tab_ethics:
        st.subheader("Ethical AI Governance")

        if ethical_rep is None:
            st.info("Run analysis to see the ethical governance assessment.")
        else:
            # Overall status badge
            status_colors = {
                "Pass":        ("#16a34a", "#f0fdf4"),
                "Conditional": ("#d97706", "#fffbeb"),
                "Fail":        ("#dc2626", "#fef2f2"),
            }
            status = ethical_rep.overall_ethical_status
            sc, sbg = status_colors.get(status, ("#6b7280", "#f9fafb"))
            st.markdown(
                f"""<div style="background:{sbg};border-left:6px solid {sc};
                padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
                <h3 style="color:{sc};margin:0">Ethical Status: {status}</h3>
                <p style="color:{sc};margin:0.5rem 0 0 0">{ethical_rep.ethical_clearance_text}</p>
                </div>""",
                unsafe_allow_html=True,
            )

            if ethical_rep.requires_expert_review:
                st.error("EXPERT REVIEW REQUIRED before using predictions in personnel decisions.")

            bias = ethical_rep.bias_audit
            st.markdown(f"**Bias Audit Summary:** {bias.audit_summary}")

            if bias.protected_attributes:
                st.subheader("Protected Attributes Detected")
                rows = []
                for attr in bias.protected_attributes:
                    rows.append({
                        "Column":      attr.column_name,
                        "Type":        attr.attribute_type.title(),
                        "Confidence":  f"{attr.detection_confidence:.0%}",
                        "Unique Values": len(attr.unique_values),
                        "Low Representation": "⚠️ Yes" if attr.representation_warning else "✅ No",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            if bias.fairness_metrics:
                st.subheader("Fairness Metrics")
                rows = []
                risk_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "acceptable": "✅"}
                for m in bias.fairness_metrics:
                    rows.append({
                        "Attribute":      m.attribute_column,
                        "Metric":         m.metric_name.replace("_", " ").title(),
                        "Risk Level":     f"{risk_icons.get(m.risk_level, '')} {m.risk_level.title()}",
                        "Disparity Ratio": f"{m.disparity_ratio:.2f}x",
                        "Fairness Score": f"{m.score:.2f}",
                        "Interpretation": m.interpretation[:80] + "...",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # Disparity bar chart
                fig = go.Figure()
                for m in bias.fairness_metrics:
                    for group, rate in m.group_rates.items():
                        fig.add_trace(go.Bar(
                            name=f"{m.attribute_column} – {group}",
                            x=[group], y=[rate],
                            text=[f"{rate:.1%}"],
                            textposition="outside",
                        ))
                if bias.fairness_metrics:
                    fig.update_layout(
                        title="Group Rates by Protected Attribute",
                        yaxis_title="Rate",
                        barmode="group",
                        height=350,
                    )
                    st.plotly_chart(fig, use_container_width=True)

            if ethical_rep.blocking_issues:
                st.error("Blocking Issues:")
                for issue in ethical_rep.blocking_issues:
                    st.error(issue)

            if ethical_rep.advisory_warnings:
                st.warning("Advisory Warnings:")
                for w in ethical_rep.advisory_warnings:
                    st.warning(w)

            with st.expander("Ethical Disclaimer"):
                st.info(bias.ethical_disclaimer)

    # ── Tab 3: Confidence ─────────────────────────────────────────────────────
    with tab_conf:
        st.subheader("Confidence & Statistical Validity")

        # Unified governance panel (primary — 5 dimensions)
        _render_unified_confidence_panel()
        st.divider()

        if conf_prof is None:
            st.info("Run analysis to see legacy confidence details.")
        else:
            band = conf_prof.confidence_band
            score = conf_prof.overall_confidence

            band_colors = {
                "High":       ("#16a34a", "#f0fdf4"),
                "Moderate":   ("#d97706", "#fffbeb"),
                "Low":        ("#ea580c", "#fff7ed"),
                "Unreliable": ("#dc2626", "#fef2f2"),
            }
            bc, bbg = band_colors.get(band, ("#6b7280", "#f9fafb"))
            st.markdown(
                f"""<div style="background:{bbg};border-left:6px solid {bc};
                padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
                <h3 style="color:{bc};margin:0">Overall Confidence: {band} ({score:.0%})</h3>
                <p style="color:{bc};margin:0.5rem 0 0 0">{conf_prof.summary}</p>
                </div>""",
                unsafe_allow_html=True,
            )

            if not conf_prof.display_threshold_met:
                st.error("Confidence below display threshold — predictions are suppressed.")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Governed Confidence", f"{score:.0%}")
            c2.metric("Calibration Score", f"{conf_prof.calibration_score:.0%}")
            c3.metric("Feature Coverage", f"{conf_prof.feature_coverage:.0%}")
            c4.metric("CV Variance", f"{conf_prof.cross_validation_variance:.4f}")

            st.divider()
            v = conf_prof.statistical_validity
            st.subheader(f"Statistical Validity: {v.level}")
            v_cols = st.columns(3)
            v_cols[0].metric("Validity Score", f"{v.confidence_score:.0%}")
            v_cols[1].metric("Sample Size Adequate", "Yes" if v.sample_size_adequate else "No")
            v_cols[2].metric("Class Balance", "Adequate" if v.class_balance_adequate else "Imbalanced")

            st.caption(f"Feature Quality: **{v.feature_quality}** · {v.data_quality_impact}")

            if v.caveats:
                st.subheader("Caveats")
                for cav in v.caveats:
                    st.warning(cav)

            # Confidence gauge
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=score * 100,
                number={"suffix": "%"},
                title={"text": "Governed Confidence"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": bc},
                    "steps": [
                        {"range": [0, 45],  "color": "#fef2f2"},
                        {"range": [45, 65], "color": "#fff7ed"},
                        {"range": [65, 80], "color": "#fffbeb"},
                        {"range": [80, 100], "color": "#f0fdf4"},
                    ],
                    "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 45},
                },
            ))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    # ── Tab 4: Provenance ─────────────────────────────────────────────────────
    with tab_provenance:
        st.subheader("Provenance Trace")
        st.caption("Full audit trail from raw data to final predictions")

        if explain_rep and hasattr(explain_rep, "provenance") and explain_rep.provenance:
            p = explain_rep.provenance
            st.markdown(
                f"""
| Property | Value |
|---|---|
| Dataset Type | {p.dataset_type} |
| Dataset Subtype | {p.dataset_subtype} |
| Input Rows | {p.n_rows_input:,} |
| Rows After Healing | {p.n_rows_after_healing:,} |
| Raw Features | {p.n_features_raw} |
| Engineered Features | {p.n_features_engineered} |
| Model Type | {p.model_type} |
| Model AUC | {p.model_auc:.4f} |
| Training Mode | {p.training_mode} |
| Target Column | {p.target_column or "None"} |
"""
            )
            if p.preprocessing_steps:
                st.subheader("Preprocessing Pipeline")
                for i, step in enumerate(p.preprocessing_steps, 1):
                    st.write(f"{i}. {step}")

            if p.feature_sources:
                st.subheader("Feature Sources")
                rows = [{"Feature": k, "Source": v} for k, v in list(p.feature_sources.items())[:20]]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Provenance trace available after running HR/supervised analysis.")

        if exec_report and exec_report.provenance_summary:
            st.divider()
            st.caption(f"**Data lineage:** {exec_report.provenance_summary}")

    # ── Tab 5: Executive Report ────────────────────────────────────────────────
    with tab_report:
        st.subheader("Auto-Generated Executive Report")

        if exec_report is None:
            st.info("Run analysis to auto-generate an executive report.")
        else:
            st.markdown(
                f"""<div style="background:#f8fafc;border:1px solid #e2e8f0;
                padding:1rem;border-radius:8px;margin-bottom:1rem">
                <h4 style="margin:0">{exec_report.report_title}</h4>
                <span style="color:#6b7280;font-size:0.85rem">
                    Generated: {exec_report.generated_at} ·
                    Confidence: {exec_report.overall_confidence} ({exec_report.overall_confidence_score:.0%})
                </span>
                </div>""",
                unsafe_allow_html=True,
            )

            if exec_report.key_findings:
                st.subheader("Key Findings")
                for f in exec_report.key_findings:
                    st.write(f"• {f}")

            if exec_report.risk_flags:
                st.subheader("Risk Flags")
                for r in exec_report.risk_flags:
                    st.error(r)

            if exec_report.recommendations:
                st.subheader("Recommendations")
                for r in exec_report.recommendations:
                    st.write(f"→ {r}")

            if exec_report.ethical_notes:
                with st.expander("Ethical Notes"):
                    for n in exec_report.ethical_notes:
                        st.info(n)

            st.divider()
            st.download_button(
                "📥 Download Executive Report (TXT)",
                data=exec_report.full_text.encode("utf-8"),
                file_name=f"executive_report_{exec_report.dataset_type}.txt",
                mime="text/plain",
                use_container_width=True,
            )


    # ── Tab 6: Leakage & Validity ─────────────────────────────────────────────
    with tab_leakage:
        st.subheader("Leakage Detection & Model Validity")

        ml_res_lv = st.session_state.get("ml_result")
        leak_rep  = getattr(ml_res_lv, "leakage_report",  None) if ml_res_lv else None
        val_rep   = getattr(ml_res_lv, "validation_report", None) if ml_res_lv else None

        if ml_res_lv is None:
            st.info("Run analysis on an HR dataset to see leakage and validity checks.")
        else:
            # ── Leakage Report ────────────────────────────────────────────────
            st.markdown("### Leakage Detection")
            if leak_rep is None:
                st.info("Leakage analysis not available for this dataset type.")
            else:
                _risk_colors = {
                    "CLEAN":    ("#16a34a", "#f0fdf4"),
                    "LOW":      ("#65a30d", "#f7fee7"),
                    "MODERATE": ("#d97706", "#fffbeb"),
                    "HIGH":     ("#ea580c", "#fff7ed"),
                    "CRITICAL": ("#dc2626", "#fef2f2"),
                }
                _rc, _rbg = _risk_colors.get(leak_rep.risk_level, ("#6b7280", "#f9fafb"))
                st.markdown(
                    f"""<div style="background:{_rbg};border-left:6px solid {_rc};
                    padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
                    <h3 style="color:{_rc};margin:0">Leakage Risk: {leak_rep.risk_level}
                    ({leak_rep.leakage_risk_score:.0%})</h3>
                    <p style="color:{_rc};margin:0.5rem 0 0 0">{leak_rep.summary}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )

                lcol1, lcol2, lcol3, lcol4 = st.columns(4)
                lcol1.metric("Risk Score",     f"{leak_rep.leakage_risk_score:.0%}")
                lcol2.metric("Critical Flags", leak_rep.n_critical,
                             delta=f"-{leak_rep.n_critical}" if leak_rep.n_critical else None,
                             delta_color="inverse")
                lcol3.metric("Governed AUC",   f"{leak_rep.governed_auc:.3f}")
                lcol4.metric("Trustworthy",    "Yes" if leak_rep.is_trustworthy else "No")

                if not leak_rep.is_trustworthy:
                    st.error(
                        f"Model predictions are NOT trustworthy due to {leak_rep.n_critical} "
                        f"critical leakage flag(s). Governed AUC capped at {leak_rep.governed_auc:.3f}."
                    )

                if leak_rep.flags:
                    st.markdown("#### Leakage Flags")
                    sev_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
                    flag_rows = []
                    for fl in leak_rep.flags:
                        flag_rows.append({
                            "Severity":       f"{sev_icons.get(fl.severity, '')} {fl.severity}",
                            "Type":           fl.flag_type.replace("_", " ").title(),
                            "Column":         fl.column or "—",
                            "Value":          f"{fl.value:.4f}" if fl.value is not None else "—",
                            "Evidence":       fl.evidence[:80],
                            "Recommendation": fl.recommendation[:80],
                        })
                    st.dataframe(pd.DataFrame(flag_rows), use_container_width=True, hide_index=True)

                if leak_rep.recommendations:
                    with st.expander("Leakage Recommendations"):
                        for rec in leak_rep.recommendations:
                            st.write(f"• {rec}")

            st.divider()

            # ── Validation Report ─────────────────────────────────────────────
            st.markdown("### Model Validity Assessment")
            if val_rep is None:
                st.info("Model validation not available for this dataset type.")
            else:
                _status_colors = {
                    "VALID":    ("#16a34a", "#f0fdf4"),
                    "DEGRADED": ("#d97706", "#fffbeb"),
                    "INVALID":  ("#dc2626", "#fef2f2"),
                }
                _sc, _sbg = _status_colors.get(val_rep.overall_status, ("#6b7280", "#f9fafb"))
                st.markdown(
                    f"""<div style="background:{_sbg};border-left:6px solid {_sc};
                    padding:1rem 1.5rem;border-radius:8px;margin-bottom:1rem">
                    <h3 style="color:{_sc};margin:0">Validation Status: {val_rep.overall_status}
                    — {val_rep.confidence_band} Confidence</h3>
                    <p style="color:{_sc};margin:0.5rem 0 0 0">{val_rep.summary}</p>
                    </div>""",
                    unsafe_allow_html=True,
                )

                vc1, vc2, vc3, vc4 = st.columns(4)
                vc1.metric("Original AUC",  f"{val_rep.original_auc:.3f}")
                vc2.metric("Governed AUC",  f"{val_rep.governed_auc:.3f}")
                vc3.metric("Deployment Safe", "Yes" if val_rep.deployment_safe else "No")
                vc4.metric("Checks Passed",  f"{val_rep.n_pass}/{val_rep.n_pass + val_rep.n_warn + val_rep.n_fail}")

                if not val_rep.deployment_safe:
                    st.error(
                        f"Model is NOT deployment-safe. {val_rep.n_fail} validation check(s) failed. "
                        f"Governed AUC capped at {val_rep.governed_auc:.3f}."
                    )

                if val_rep.checks:
                    st.markdown("#### Validation Checks")
                    chk_icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
                    chk_rows = []
                    for chk in val_rep.checks:
                        chk_rows.append({
                            "Status":         f"{chk_icons.get(chk.severity, '')} {chk.severity}",
                            "Check":          chk.check_name.replace("_", " ").title(),
                            "Value":          f"{chk.value:.4f}" if chk.value is not None else "—",
                            "Message":        chk.message[:90],
                            "Recommendation": chk.recommendation[:80],
                        })
                    st.dataframe(pd.DataFrame(chk_rows), use_container_width=True, hide_index=True)

                if val_rep.recommendations:
                    with st.expander("Validation Recommendations"):
                        for rec in val_rep.recommendations:
                            st.write(f"• {rec}")

                if val_rep.provenance:
                    with st.expander("Validation Provenance"):
                        for p in val_rep.provenance:
                            st.caption(p)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 10: Data Quality
# ─────────────────────────────────────────────────────────────────────────────

def page_quality():
    st.title("🔍 Data Quality Report")
    contract = _contract()
    prof     = st.session_state.get("profile")

    if prof is None:
        st.info("Upload a dataset first.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Quality Score", f"{prof.overall_quality_score:.0f}/100")
    c2.metric(contract.row_label().title() if contract else "Rows", f"{prof.n_rows:,}")
    c3.metric("Columns", prof.n_cols)
    c4.metric("File Size", f"{prof.file_size_mb:.2f} MB")

    if contract and contract.quality_issues:
        st.subheader("Quality Issues")
        for qi in contract.quality_issues:
            st.warning(qi)

    if prof.quality_flags:
        with st.expander("All Quality Flags"):
            for f in prof.quality_flags:
                st.warning(f)

    st.subheader("Column Type Distribution")
    tc = {
        "Numeric":     len(prof.numeric_cols),
        "Categorical": len(prof.categorical_cols),
        "Binary":      len(prof.binary_cols),
        "Datetime":    len(prof.datetime_cols),
        "Text":        len(prof.text_cols),
        "ID-like":     len(prof.id_cols),
    }
    fig = px.pie(
        values=list(tc.values()), names=list(tc.keys()),
        title="Column Type Distribution",
    )
    st.plotly_chart(fig, use_container_width=True)

    if prof.missing_summary:
        st.subheader("Missing Data")
        mdf = pd.DataFrame(
            [(c, f"{v:.1%}") for c, v in prof.missing_summary.items()],
            columns=["Column", "Missing Rate"],
        )
        st.dataframe(mdf, use_container_width=True, hide_index=True)

    st.subheader("Column Profiles")
    rows = []
    for col, cp in prof.columns.items():
        row = {"Column": col, "Type": cp.inferred_type,
               "Missing": f"{cp.missing_rate:.0%}", "Unique": cp.n_unique}
        if cp.mean is not None:
            row["Mean"] = f"{cp.mean:.2f}"
            row["Std"]  = f"{cp.std:.2f}" if cp.std else "—"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ROUTER
# ─────────────────────────────────────────────────────────────────────────────

def main():
    _init()
    page = _sidebar()
    # All 10 pages route to extracted modules when available; inline defs are fallbacks only
    dispatch = {
        "Adaptive Dataset Intelligence":   (
            (lambda: _adaptive_mod.render(run_analysis_fn=_run_analysis))
            if _MODULAR else page_adaptive
        ),
        "HR Attrition Analytics":          (_hr_attrition_mod.render    if _MODULAR else page_hr_attrition),
        "Psychological Risk Intelligence": (_psychological_mod.render   if _MODULAR else page_psychological),
        "Biosignal Intelligence":          (_biosignal_mod.render       if _MODULAR else page_biosignal),
        "Time-Series Early Warning":       (_timeseries_mod.render      if _MODULAR else page_timeseries),
        "Department & Org Risk":           (_department_mod.render      if _MODULAR else page_department),
        "Executive Insights & Actions":    (_insights_mod.render        if _MODULAR else page_insights),
        "Model & AutoML Analytics":        (_model_mod.render           if _MODULAR else page_model),
        "Explainability & Governance":     (_explainability_mod.render  if _MODULAR else page_explainability),
        "Data Quality Report":             (_quality_mod.render         if _MODULAR else page_quality),
    }
    _default_fn = (
        (lambda: _adaptive_mod.render(run_analysis_fn=_run_analysis)) if _MODULAR else page_adaptive
    )
    page_fn = dispatch.get(page, _default_fn)
    try:
        page_fn()
    except Exception as _page_exc:
        import traceback as _tb
        st.error(
            "An unexpected error occurred on this page. "
            "Please try re-uploading your dataset or selecting a different page."
        )
        with st.expander("Technical details (for support)"):
            st.code(_tb.format_exc(), language="text")


if __name__ == "__main__":
    main()
