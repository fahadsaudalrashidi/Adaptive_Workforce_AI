"""
Explainability & Governance Page
SHAP feature importance, provenance traces, bias audits, and confidence governance.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components.governance_panel import (
    render_unified_confidence_panel, render_feature_trust_panel, render_calibration_panel,
)
from frontend.utils.safe_render import safe_error_boundary
from frontend.utils.session_helpers import require_analysis


def render() -> None:
    st.title("Explainability & Governance")
    st.caption("SHAP feature importance, provenance traces, bias audits, and confidence governance")

    if not require_analysis():
        return

    explain_rep = st.session_state.get("explain_report")
    ethical_rep = st.session_state.get("ethical_report")
    conf_prof   = st.session_state.get("confidence_profile")
    exec_report = st.session_state.get("exec_report")
    ml_res      = st.session_state.get("ml_result")

    tab_explain, tab_ethics, tab_conf, tab_provenance, tab_report, tab_leakage = st.tabs([
        "Explainability",
        "Ethical Governance",
        "Confidence",
        "Provenance",
        "Executive Report",
        "Leakage & Validity",
    ])

    with tab_explain:
        with safe_error_boundary("Explainability"):
            st.subheader("Feature Importance & Explainability")
            if explain_rep is None:
                st.info("Run analysis on an HR dataset to see explainability.")
            else:
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

                if explain_rep.top_features:
                    rows = [{
                        "Feature":     ff.feature_name,
                        "Importance":  f"{ff.importance_score:.4f}",
                        "Direction":   ff.direction.replace("_", " ").title(),
                        "Magnitude":   ff.magnitude.title(),
                        "Explanation": ff.plain_english,
                        "Data Source": ff.data_source,
                    } for ff in explain_rep.top_features]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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

                if explain_rep.reasoning_chain:
                    with st.expander("Reasoning Chain"):
                        for i, step in enumerate(explain_rep.reasoning_chain, 1):
                            st.write(f"{i}. {step}")

                if explain_rep.uncertainty_note:
                    st.warning(explain_rep.uncertainty_note)

            st.divider()
            render_feature_trust_panel()

    with tab_ethics:
        with safe_error_boundary("Ethical Governance"):
            st.subheader("Ethical AI Governance")
            if ethical_rep is None:
                st.info("Run analysis to see the ethical governance assessment.")
            else:
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
                    rows = [{
                        "Column":      attr.column_name,
                        "Type":        attr.attribute_type.title(),
                        "Confidence":  f"{attr.detection_confidence:.0%}",
                        "Unique Values": len(attr.unique_values),
                        "Low Representation": "Yes" if attr.representation_warning else "No",
                    } for attr in bias.protected_attributes]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                if bias.fairness_metrics:
                    st.subheader("Fairness Metrics")
                    risk_icons = {"critical": "CRIT", "high": "HIGH", "medium": "MED",
                                  "low": "LOW", "acceptable": "OK"}
                    rows = [{
                        "Attribute":       m.attribute_column,
                        "Metric":          m.metric_name.replace("_", " ").title(),
                        "Risk Level":      f"{risk_icons.get(m.risk_level, '')} {m.risk_level.title()}",
                        "Disparity Ratio": f"{m.disparity_ratio:.2f}x",
                        "Fairness Score":  f"{m.score:.2f}",
                        "Interpretation":  m.interpretation[:80] + "...",
                    } for m in bias.fairness_metrics]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    fig = go.Figure()
                    for m in bias.fairness_metrics:
                        for group, rate in m.group_rates.items():
                            fig.add_trace(go.Bar(
                                name=f"{m.attribute_column} - {group}",
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

    with tab_conf:
        with safe_error_boundary("Confidence"):
            st.subheader("Confidence & Statistical Validity")
            render_unified_confidence_panel()
            render_calibration_panel()
            st.divider()

            if conf_prof is None:
                st.info("Run analysis to see legacy confidence details.")
            else:
                band  = conf_prof.confidence_band
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
                        "threshold": {"line": {"color": "red", "width": 4},
                                      "thickness": 0.75, "value": 45},
                    },
                ))
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

    with tab_provenance:
        with safe_error_boundary("Provenance Trace"):
            st.subheader("Provenance Trace")
            st.caption("Full audit trail from raw data to final predictions")
            if explain_rep and hasattr(explain_rep, "provenance") and explain_rep.provenance:
                p = explain_rep.provenance
                st.markdown(f"""
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
""")
                if p.preprocessing_steps:
                    st.subheader("Preprocessing Pipeline")
                    for i, step in enumerate(p.preprocessing_steps, 1):
                        st.write(f"{i}. {step}")
                if p.feature_sources:
                    st.subheader("Feature Sources")
                    rows = [{"Feature": k, "Source": v}
                            for k, v in list(p.feature_sources.items())[:20]]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Provenance trace available after running HR/supervised analysis.")
            if exec_report and exec_report.provenance_summary:
                st.divider()
                st.caption(f"**Data lineage:** {exec_report.provenance_summary}")

    with tab_report:
        with safe_error_boundary("Executive Report"):
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
                        st.write(f"- {f}")
                if exec_report.risk_flags:
                    st.subheader("Risk Flags")
                    for r in exec_report.risk_flags:
                        st.error(r)
                if exec_report.recommendations:
                    st.subheader("Recommendations")
                    for r in exec_report.recommendations:
                        st.write(f"-> {r}")
                if exec_report.ethical_notes:
                    with st.expander("Ethical Notes"):
                        for n in exec_report.ethical_notes:
                            st.info(n)
                st.divider()
                st.download_button(
                    "Download Executive Report (TXT)",
                    data=exec_report.full_text.encode("utf-8"),
                    file_name=f"executive_report_{exec_report.dataset_type}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

    with tab_leakage:
        with safe_error_boundary("Leakage & Validity"):
            st.subheader("Leakage Detection & Model Validity")
            ml_res_lv = st.session_state.get("ml_result")
            leak_rep  = getattr(ml_res_lv, "leakage_report",    None) if ml_res_lv else None
            val_rep   = getattr(ml_res_lv, "validation_report", None) if ml_res_lv else None

            if ml_res_lv is None:
                st.info("Run analysis on an HR dataset to see leakage and validity checks.")
            else:
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
                    lcol2.metric("Critical Flags", leak_rep.n_critical)
                    lcol3.metric("Governed AUC",   f"{leak_rep.governed_auc:.3f}")
                    lcol4.metric("Trustworthy",    "Yes" if leak_rep.is_trustworthy else "No")

                    if not leak_rep.is_trustworthy:
                        st.error(
                            f"Model predictions are NOT trustworthy due to {leak_rep.n_critical} "
                            f"critical leakage flag(s). Governed AUC capped at {leak_rep.governed_auc:.3f}."
                        )
                    if leak_rep.flags:
                        st.markdown("#### Leakage Flags")
                        flag_rows = [{
                            "Severity":       fl.severity,
                            "Type":           fl.flag_type.replace("_", " ").title(),
                            "Column":         fl.column or "-",
                            "Value":          f"{fl.value:.4f}" if fl.value is not None else "-",
                            "Evidence":       fl.evidence[:80],
                            "Recommendation": fl.recommendation[:80],
                        } for fl in leak_rep.flags]
                        st.dataframe(pd.DataFrame(flag_rows), use_container_width=True, hide_index=True)
                    if leak_rep.recommendations:
                        with st.expander("Leakage Recommendations"):
                            for rec in leak_rep.recommendations:
                                st.write(f"- {rec}")

                st.divider()
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
                    vc1.metric("Original AUC",   f"{val_rep.original_auc:.3f}")
                    vc2.metric("Governed AUC",   f"{val_rep.governed_auc:.3f}")
                    vc3.metric("Deployment Safe", "Yes" if val_rep.deployment_safe else "No")
                    vc4.metric("Checks Passed",
                               f"{val_rep.n_pass}/{val_rep.n_pass + val_rep.n_warn + val_rep.n_fail}")

                    if not val_rep.deployment_safe:
                        st.error(
                            f"Model is NOT deployment-safe. {val_rep.n_fail} validation check(s) failed. "
                            f"Governed AUC capped at {val_rep.governed_auc:.3f}."
                        )
                    if val_rep.checks:
                        st.markdown("#### Validation Checks")
                        chk_rows = [{
                            "Status":         chk.severity,
                            "Check":          chk.check_name.replace("_", " ").title(),
                            "Value":          f"{chk.value:.4f}" if chk.value is not None else "-",
                            "Message":        chk.message[:90],
                            "Recommendation": chk.recommendation[:80],
                        } for chk in val_rep.checks]
                        st.dataframe(pd.DataFrame(chk_rows), use_container_width=True, hide_index=True)
                    if val_rep.recommendations:
                        with st.expander("Validation Recommendations"):
                            for rec in val_rep.recommendations:
                                st.write(f"- {rec}")
                    if val_rep.provenance:
                        with st.expander("Validation Provenance"):
                            for p in val_rep.provenance:
                                st.caption(p)
