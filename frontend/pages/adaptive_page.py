"""
Adaptive Dataset Intelligence Page
Universal routing engine — detects any dataset type and enforces scientifically valid analysis.
Displays contract, compatibility matrix, column mapping, sandbox validation, and analysis launcher.

Note: run_analysis_fn is injected from app.py to avoid circular import.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Callable

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

from frontend.utils.safe_render import safe_error_boundary
from frontend.utils.session_helpers import get_contract
from backend.core.dataset_contract import DatasetContract
from backend.core.biosignal_adapter import BiosignalProfile
from config.settings import (
    PLATFORM_NAME, PLATFORM_VERSION, REPORT_VERSION,
    DEFAULT_CURRENCY, CURRENCY_SYMBOLS, HUMAN_OVERSIGHT_DISCLAIMER,
)

# ── Dataset type → (border, background) color map ─────────────────────────────
_TYPE_COLORS: dict[str, tuple[str, str]] = {
    "hr_attrition":         ("#1e40af", "#dbeafe"),
    "hr_workforce":         ("#1e3a5f", "#cfe2ff"),
    "biosignal_timeseries": ("#065f46", "#d1fae5"),
    "psychological_survey": ("#7c3aed", "#ede9fe"),
    "burnout_survey":       ("#9d174d", "#fce7f3"),
    "generic_timeseries":   ("#92400e", "#fef3c7"),
    "mixed_enterprise":     ("#be185d", "#fce7f3"),
    "unknown":              ("#374151", "#f3f4f6"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_styled_df(df: pd.DataFrame, styler_func=None, **kwargs) -> None:
    if styler_func is not None:
        try:
            st.dataframe(df.style.apply(styler_func, axis=1), **kwargs)
            return
        except Exception as exc:
            msg = str(exc).lower()
            if "jinja2" in msg or "style" in msg or "styler" in msg:
                st.dataframe(df, **kwargs)
                return
            raise
    st.dataframe(df, **kwargs)


def _render_contract_banner(contract: DatasetContract) -> None:
    bg, fg = _TYPE_COLORS.get(contract.dataset_type, ("#374151", "#f3f4f6"))
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


def _render_metric_card(contract: DatasetContract, n_rows: int, n_cols: int,
                         quality: float, target: Optional[str]) -> None:
    row_label = contract.row_label().title()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Total {row_label}", f"{n_rows:,}")
    c2.metric("Columns", n_cols)
    c3.metric("Quality Score", f"{quality:.0f}/100")

    if contract.is_biosignal:
        c4.metric("Signal Type", contract.detected_signal_type or "Signal")
    elif contract.target_available:
        c4.metric("Target Column", target or "—")
    else:
        c4.metric("Supervised Prediction", "Not available (no target)")

    if contract.is_biosignal:
        bio_prof: Optional[BiosignalProfile] = st.session_state.get("biosignal_profile")
        if bio_prof:
            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            r2c1.metric("Windows Analysed", f"{bio_prof.n_windows:,}")
            r2c2.metric("Signal Quality", f"{bio_prof.quality_score:.0f}/100")
            r2c3.metric("Anomaly Count", bio_prof.anomaly_count)
            r2c4.metric("Stress Proxy Level", bio_prof.stress_level_label)


def _show_supported_types() -> None:
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


# ── Tab renderers ─────────────────────────────────────────────────────────────

def _tab_compat(contract: DatasetContract) -> None:
    st.subheader("Analysis Compatibility Matrix")
    st.caption("Every analysis checked against the DatasetContract — no exceptions")
    rows = [
        {
            "Analysis":  entry.label,
            "Available": "✅ Yes" if entry.available else "❌ No",
            "Reason":    entry.reason,
        }
        for entry in contract.compatibility_matrix
    ]
    mdf = pd.DataFrame(rows)

    def _style_row(row):
        color = "#f0fdf4" if "Yes" in row["Available"] else "#fef2f2"
        return [f"background-color: {color}"] * len(row)

    _safe_styled_df(mdf, _style_row, use_container_width=True, hide_index=True)


def _tab_map(contract: DatasetContract) -> None:
    st.subheader("Semantic Column Mapping")
    sem_map = st.session_state.get("sem_map")
    if sem_map:
        rows = [
            {
                "Column": col,
                "Semantic Category": m.semantic_category,
                "Confidence": f"{m.confidence:.0%}",
                "Method": m.method,
            }
            for col, m in sem_map.mappings.items()
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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
            st.warning(
                f"Protected attributes: **{', '.join(sm_v2.protected_attributes)}** "
                "— fairness audit recommended"
            )
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


def _tab_sandbox(contract: DatasetContract) -> None:
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
                icon = "✅" if guard_result.allowed else "❌"
                status = "ALLOWED" if guard_result.allowed else "BLOCKED"
                st.markdown(f"{icon} **{analysis_key}** — {status}")
                for v in (guard_result.violations or []):
                    st.caption(f"   Violation: {v.message}")
                for w in (guard_result.warnings or []):
                    st.caption(f"   Warning: {w.message}")
    else:
        st.info("Phase 3 sandbox results not yet available for this dataset.")


def _tab_run(contract: DatasetContract, df: pd.DataFrame,
             run_fn: Optional[Callable]) -> None:
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
        if run_fn is not None:
            run_fn(target_override)
        if st.session_state.get("analysis_done"):
            st.success("✅ Analysis complete!")
            if contract.is_biosignal:
                st.info("→ Navigate to **Biosignal Intelligence** to view results.")
            else:
                st.info("→ Navigate to HR Attrition, Insights, or other pages to explore results.")


# ── Export helpers ─────────────────────────────────────────────────────────────

def _build_csv_export() -> bytes:
    contract = get_contract()
    df_eng   = st.session_state.get("df_eng")
    bio_prof = st.session_state.get("biosignal_profile")
    if contract and contract.is_biosignal and bio_prof and bio_prof.window_features_df is not None:
        return bio_prof.window_features_df.to_csv(index=False).encode("utf-8")
    if df_eng is not None:
        return df_eng.to_csv(index=False).encode("utf-8")
    return b""


def _tab_export() -> None:
    contract = get_contract()
    if contract is None:
        st.info("Upload a dataset to enable export.")
        return
    if not st.session_state.get("analysis_done"):
        st.info("Run analysis first.")
        return

    st.subheader("📄 Export Report")
    currency     = st.session_state.get("currency", DEFAULT_CURRENCY)
    currency_sym = CURRENCY_SYMBOLS.get(currency, currency)

    if contract.is_biosignal:
        st.info("**Biosignal Stress Intelligence Report** will be generated.")
        _export_biosignal(currency_sym)
    elif contract.is_hr and contract.allows("pdf_report"):
        st.info("**Workforce Intelligence PDF Report** will be generated.")
        _export_hr(currency_sym, currency)
    elif contract.is_survey:
        st.info("**Psychological Risk Report** will be generated.")
        _export_survey()
    else:
        st.info("**Dataset Profiling Report** will be generated.")
        _export_profiling()


def _export_biosignal(currency_sym: str) -> None:
    bio_prof = st.session_state.get("biosignal_profile")
    if bio_prof is None:
        st.warning("No biosignal profile available.")
        return

    lines = [
        "=" * 60, "BIOSIGNAL STRESS INTELLIGENCE REPORT",
        f"Signal Type: {bio_prof.canonical_name}",
        f"Row Unit: {bio_prof.row_unit}",
        "=" * 60, "",
        "NON-CLINICAL DISCLAIMER:", bio_prof.disclaimer, "",
        "SIGNAL OVERVIEW:",
        f"  Total Signal Samples: {bio_prof.n_samples:,}",
        f"  Windows Analysed:     {bio_prof.n_windows:,}",
        f"  Duration:             {bio_prof.duration_seconds:.0f} seconds",
        f"  Sampling Frequency:   {bio_prof.estimated_fs:.1f} Hz",
        f"  Missing Rate:         {bio_prof.missing_rate:.1%}",
        "", "SIGNAL QUALITY:",
        f"  Quality Score:  {bio_prof.quality_score:.0f}/100",
        f"  Anomaly Count:  {bio_prof.anomaly_count}",
        "", "PHYSIOLOGICAL STRESS PROXY:",
        f"  Stress Level:          {bio_prof.stress_level_label}",
        f"  Stress Signal Score:   {bio_prof.stress_signal_score:.4f}",
        f"  Fatigue Signal Score:  {bio_prof.fatigue_signal_score:.4f}",
        f"  Instability Score:     {bio_prof.physiological_instability:.4f}",
        f"  Volatility Score:      {bio_prof.signal_volatility_score:.4f}",
        f"  Anomaly Risk Score:    {bio_prof.anomaly_risk_score:.4f}",
        f"  Biosignal Confidence:  {bio_prof.biosignal_confidence:.4f}",
        "", "EARLY WARNING STATUS:",
        f"  {bio_prof.early_warning_status}",
        f"  {bio_prof.stress_level_description}",
        "", "GLOBAL SIGNAL STATISTICS:",
    ]
    for k, v in bio_prof.global_stats.items():
        lines.append(f"  {k}: {v:.4f}")
    lines += [
        "", "LIMITATIONS:",
        "  These scores are derived from wearable sensor data.",
        "  They do not constitute medical or clinical diagnoses.",
        "  Individual variation, device placement, and movement",
        "  artifacts may affect signal quality and score accuracy.",
        "  Consult a qualified medical professional for any clinical",
        "  interpretation of physiological data.",
        "", "=" * 60,
        f"Generated by {PLATFORM_NAME} v{PLATFORM_VERSION}",
    ]

    report_text = "\n".join(lines)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Download Biosignal Report (TXT)",
            data=report_text.encode("utf-8"),
            file_name=f"biosignal_{bio_prof.signal_type.lower()}_report.txt",
            mime="text/plain", use_container_width=True,
        )
    with col2:
        csv_data = _build_csv_export()
        if csv_data:
            st.download_button(
                "📥 Download Window Features (CSV)",
                data=csv_data,
                file_name=f"biosignal_{bio_prof.signal_type.lower()}_windows.csv",
                mime="text/csv", use_container_width=True,
            )


def _export_hr(currency_sym: str, currency: str) -> None:
    import datetime as _dt

    org_risk    = st.session_state.get("org_risk")
    dept_risks  = st.session_state.get("dept_risks") or []
    insight_rep = st.session_state.get("insight_report")
    exec_rep    = st.session_state.get("exec_report")
    ucr         = st.session_state.get("unified_confidence")
    contract    = get_contract()
    now_str     = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "=" * 72,
        f"  {PLATFORM_NAME}",
        f"  WORKFORCE INTELLIGENCE REPORT  (v{REPORT_VERSION})",
        f"  Generated: {now_str}",
        f"  Currency: {currency_sym}",
        "=" * 72, "",
        "IMPORTANT NOTICE", "-" * 40,
        "  " + HUMAN_OVERSIGHT_DISCLAIMER, "",
    ]

    if ucr:
        lines += [
            "AI RELIABILITY & GOVERNANCE SUMMARY", "-" * 40,
            f"  Data Quality:       {ucr.data_quality.band} ({ucr.data_quality.score:.0%})",
            f"  Routing Confidence: {ucr.routing_confidence.band} ({ucr.routing_confidence.score:.0%})",
            f"  Model Reliability:  {ucr.model_reliability.band} ({ucr.model_reliability.score:.0%})",
            f"  Analysis Confidence:{ucr.analysis_confidence.band} ({ucr.analysis_confidence.score:.0%})",
            f"  Leakage Risk:       {ucr.leakage_risk_score:.0%}",
            f"  Executive Readiness:{ucr.executive_readiness}", "",
        ]

    if org_risk:
        row_lbl = contract.row_label().title() if contract else "Records"
        lines += [
            "WORKFORCE RISK SUMMARY", "-" * 40,
            f"  Total {row_lbl}:       {org_risk.total_employees:,}",
            f"  Predicted Attrition Rate: {org_risk.overall_attrition_risk:.1%}",
            f"  Priority Review Segment:  {org_risk.high_risk_employees:,} records "
            "(flagged for HR review, not automated action)",
            f"  Sustainability Score:      {org_risk.sustainability_score:.0f}/100",
            f"  Estimated Exposure:        {currency_sym} {org_risk.total_financial_exposure:,.0f}",
            f"  Early Warning Level:       {org_risk.early_warning_level}", "",
        ]

    if dept_risks:
        lines += ["DEPARTMENT-LEVEL ANALYSIS", "-" * 40]
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
            "DEPARTMENT-LEVEL ANALYSIS", "-" * 40,
            "  Department-level analysis unavailable — no department column detected.", "",
        ]

    if insight_rep:
        lines += [
            "EXECUTIVE SUMMARY", "-" * 40,
            "  " + insight_rep.executive_summary, "",
            "KEY INSIGHTS", "-" * 40,
        ]
        for ins in insight_rep.insights[:5]:
            lines.append(f"  [{ins.category.upper()}] {ins.title}")
            lines.append(f"    {ins.body[:140]}")
        lines.append("")
        if insight_rep.recommended_actions_30d:
            lines += ["30-DAY HR REVIEW PLAN", "-" * 40]
            for a in insight_rep.recommended_actions_30d:
                lines.append(f"  - {a}")
            lines.append("")

    lines += [
        "LIMITATIONS", "-" * 40,
        "  - Predictions are probabilistic estimates, not certainties.",
        "  - Results are dataset-specific and may not generalise.",
        "  - Human judgment is required before any workforce action.",
        "  - This report must not be used for automated personnel decisions.", "",
        "=" * 72,
        f"  {PLATFORM_NAME} v{PLATFORM_VERSION}  |  Report v{REPORT_VERSION}",
        "=" * 72,
    ]

    report_text = "\n".join(lines)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Download Report (TXT)", data=report_text.encode("utf-8"),
            file_name=f"workforce_intelligence_report_{currency}.txt",
            mime="text/plain", use_container_width=True,
        )
    with col2:
        if exec_rep and hasattr(exec_rep, "html_text") and exec_rep.html_text:
            st.download_button(
                "Download Report (HTML)", data=exec_rep.html_text.encode("utf-8"),
                file_name="workforce_intelligence_report.html",
                mime="text/html", use_container_width=True,
            )
        else:
            st.caption("HTML report: run analysis to generate.")
    with col3:
        csv_data = _build_csv_export()
        if csv_data:
            st.download_button(
                "Download Engineered Data (CSV)", data=csv_data,
                file_name="hr_features.csv", mime="text/csv", use_container_width=True,
            )


def _export_survey() -> None:
    insight_rep = st.session_state.get("insight_report")
    contract    = get_contract()
    lines = [
        "=" * 60, "PSYCHOLOGICAL RISK SURVEY REPORT",
        f"Dataset Type: {contract.dataset_type.replace('_', ' ').title() if contract else 'Survey'}",
        "=" * 60, "",
    ]
    if insight_rep:
        lines += ["EXECUTIVE SUMMARY:", insight_rep.executive_summary, ""]
    lines += ["=" * 60, f"Generated by {PLATFORM_NAME} v{PLATFORM_VERSION}"]
    st.download_button(
        "📥 Download Survey Report (TXT)",
        data="\n".join(lines).encode("utf-8"),
        file_name="psychological_risk_report.txt",
        mime="text/plain", use_container_width=True,
    )


def _export_profiling() -> None:
    prof     = st.session_state.get("profile")
    contract = get_contract()
    lines = [
        "=" * 60, "DATASET PROFILING REPORT",
        f"Dataset Type: {contract.dataset_type.replace('_', ' ').title() if contract else 'Unknown'}",
        "=" * 60, "",
    ]
    if prof:
        lines += [
            f"Rows:          {prof.n_rows:,}",
            f"Columns:       {prof.n_cols}",
            f"Quality Score: {prof.overall_quality_score:.0f}/100",
            f"File Size:     {prof.file_size_mb:.2f} MB",
            "", "COLUMN SUMMARY:",
        ]
        for col, cp in list(prof.columns.items())[:20]:
            lines.append(
                f"  {col}: {cp.inferred_type}, {cp.missing_rate:.0%} missing, {cp.n_unique} unique"
            )
    lines += ["", "=" * 60, f"Generated by {PLATFORM_NAME} v{PLATFORM_VERSION}"]
    st.download_button(
        "📥 Download Profiling Report (TXT)",
        data="\n".join(lines).encode("utf-8"),
        file_name="dataset_profiling_report.txt",
        mime="text/plain", use_container_width=True,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def render(run_analysis_fn: Optional[Callable] = None) -> None:
    """Render the Adaptive Dataset Intelligence page.

    Args:
        run_analysis_fn: The analysis pipeline callable from app.py (_run_analysis).
                         Injected at dispatch time to avoid circular imports.
    """
    st.title("🧠 Adaptive Dataset Intelligence")
    st.caption(
        "Universal routing engine — detects any dataset type "
        "and enforces scientifically valid analysis"
    )

    df       = st.session_state.get("df")
    prof     = st.session_state.get("profile")
    contract = get_contract()

    if df is None:
        st.info("Upload a dataset using the sidebar to begin.")
        _show_supported_types()
        return

    with safe_error_boundary("Contract Banner"):
        _render_contract_banner(contract)

    with safe_error_boundary("Warning Messages"):
        for w in (contract.warning_messages or []):
            st.warning(w)

    with safe_error_boundary("Metric Cards"):
        _render_metric_card(
            contract, prof.n_rows, prof.n_cols,
            contract.quality_score, contract.target_column,
        )

    with safe_error_boundary("Quality Issues"):
        if contract.quality_issues:
            with st.expander("⚠️ Quality Issues"):
                for issue in contract.quality_issues:
                    st.warning(issue)

    if contract.is_biosignal:
        with safe_error_boundary("Biosignal Notice"):
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
        "📋 Compatibility Matrix",
        "🗺️ Column Mapping",
        "🛡️ Sandbox Intelligence",
        "🚀 Run Analysis",
        "📄 Export Report",
    ])

    with tab_compat:
        with safe_error_boundary("Compatibility Matrix"):
            _tab_compat(contract)

    with tab_map:
        with safe_error_boundary("Column Mapping"):
            _tab_map(contract)

    with tab_sandbox:
        with safe_error_boundary("Sandbox Validation"):
            _tab_sandbox(contract)

    with tab_run:
        with safe_error_boundary("Run Analysis"):
            _tab_run(contract, df, run_analysis_fn)

    with tab_export:
        with safe_error_boundary("Export Report"):
            _tab_export()
