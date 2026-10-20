"""
Autonomous Report Generator
Produces confidence-annotated, provenance-traced, executive-ready reports
for any dataset type the Adaptive Workforce Intelligence Engine encounters.

Enterprise standards:
- All predictions described as decision-support signals, not automated decisions
- Financial exposure in configured currency (default SAR)
- Version pulled from settings (single source of truth)
- HTML + clean TXT export formats
- Associative language only — no causal claims
"""
from __future__ import annotations

import datetime
import html as _html_escape
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore")

from config.settings import (
    PLATFORM_NAME, PLATFORM_VERSION, REPORT_VERSION,
    HUMAN_OVERSIGHT_DISCLAIMER, DEFAULT_CURRENCY, CURRENCY_SYMBOLS,
)


# ── Report dataclasses ───────────────────────────────────────────────────────

@dataclass
class ReportSection:
    title: str
    content: str
    confidence_band: str        # "High" / "Moderate" / "Low" / "N/A"
    confidence_score: float     # 0–1
    section_type: str           # "insight" / "warning" / "metric" / "disclaimer"
    caveats: List[str] = field(default_factory=list)


@dataclass
class ExecutiveReport:
    report_title: str
    dataset_type: str
    dataset_subtype: str
    generated_at: str           # ISO datetime string
    overall_confidence: str     # "High" / "Moderate" / "Low" / "Unreliable"
    overall_confidence_score: float
    sections: List[ReportSection]
    key_findings: List[str]
    risk_flags: List[str]
    ethical_notes: List[str]
    recommendations: List[str]
    methodology_note: str
    data_quality_summary: str
    provenance_summary: str
    full_text: str              # Pre-rendered plain-text version for download
    html_text: str = ""         # HTML report version
    currency: str = "SAR"
    platform_version: str = PLATFORM_VERSION
    report_version: str = REPORT_VERSION


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _confidence_label(score: float) -> str:
    if score >= 0.80:
        return "High"
    if score >= 0.65:
        return "Moderate"
    if score >= 0.50:
        return "Low"
    return "Unreliable"


def _fmt_pct(v: float) -> str:
    return f"{v:.1%}"


def _fmt_float(v: float, dp: int = 3) -> str:
    return f"{v:.{dp}f}"


def _section_divider(title: str, width: int = 72) -> str:
    bar = "=" * width
    return f"\n{bar}\n  {title}\n{bar}\n"


def _conf_badge(band: str) -> str:
    badges = {
        "High":       "[CONFIDENCE: HIGH  ✓]",
        "Moderate":   "[CONFIDENCE: MODERATE ~]",
        "Low":        "[CONFIDENCE: LOW  !]",
        "Unreliable": "[CONFIDENCE: UNRELIABLE ✗]",
        "N/A":        "[CONFIDENCE: N/A]",
    }
    return badges.get(band, "[CONFIDENCE: UNKNOWN]")


# ── Report Generator ─────────────────────────────────────────────────────────

class ReportGenerator:
    """
    Builds structured executive reports from analysis results.
    All output is confidence-annotated and provenance-traced.
    """

    def generate_hr_report(
        self,
        *,
        dataset_type: str,
        dataset_subtype: str,
        n_rows: int,
        n_features: int,
        data_quality_score: float,
        target_column: Optional[str],
        model_type: str,
        auc_score: float,
        training_mode: str,
        top_features: List[Dict[str, Any]],
        attrition_rate: Optional[float],
        risk_distribution: Optional[Dict[str, int]],
        bias_risk_level: str,
        ethical_disclaimer: str,
        provenance_steps: List[str],
        caveats: List[str],
        governed_confidence: float,
        currency: str = DEFAULT_CURRENCY,
        # Scientific validity inputs (optional — from governance pipeline)
        original_auc: Optional[float] = None,
        governed_auc: Optional[float] = None,
        leakage_risk_score: float = 0.0,
        leakage_n_critical: int = 0,
        leakage_n_high: int = 0,
        calibration_quality_label: str = "Not Evaluated",
        brier_score: Optional[float] = None,
        calibration_ece: Optional[float] = None,
        model_reliability_score: Optional[float] = None,
    ) -> ExecutiveReport:

        generated_at = _now_str()
        conf_band = _confidence_label(governed_confidence)

        sections: List[ReportSection] = []

        # — Dataset Overview —
        quality_desc = (
            "Excellent" if data_quality_score >= 0.85 else
            "Good"      if data_quality_score >= 0.70 else
            "Fair"      if data_quality_score >= 0.55 else
            "Poor"
        )
        overview_content = (
            f"Dataset type   : {dataset_type} / {dataset_subtype}\n"
            f"Records        : {n_rows:,}\n"
            f"Features used  : {n_features}\n"
            f"Data quality   : {quality_desc} ({data_quality_score:.0%})\n"
            f"Target column  : {target_column or 'None detected'}\n"
            f"Analysis date  : {generated_at}"
        )
        sections.append(ReportSection(
            title="Dataset Overview",
            content=overview_content,
            confidence_band="N/A",
            confidence_score=1.0,
            section_type="metric",
        ))

        # — Model Performance —
        model_section_conf = governed_confidence
        model_content = (
            f"Model type     : {model_type}\n"
            f"Training mode  : {training_mode}\n"
            f"AUC-ROC        : {auc_score:.4f}\n"
            f"Performance    : {'Good (AUC ≥ 0.75)' if auc_score >= 0.75 else 'Moderate (0.65–0.75)' if auc_score >= 0.65 else 'Limited (< 0.65)'}\n"
            f"Governed conf. : {governed_confidence:.0%} [{conf_band}]"
        )
        sections.append(ReportSection(
            title="Model Performance",
            content=model_content,
            confidence_band=conf_band,
            confidence_score=model_section_conf,
            section_type="metric",
            caveats=[c for c in caveats if "model" in c.lower() or "auc" in c.lower()],
        ))

        # — Attrition Risk Summary —
        if attrition_rate is not None:
            risk_content = f"Predicted attrition rate : {_fmt_pct(attrition_rate)}\n"
            if risk_distribution:
                for label, count in risk_distribution.items():
                    pct = count / n_rows if n_rows else 0
                    # Relabel "high risk" buckets to governance-safe language
                    safe_label = label.replace("High Risk", "Priority Review").replace("high risk", "priority review")
                    risk_content += f"  {safe_label:<24}: {count:>6,} ({pct:.1%})\n"
            sections.append(ReportSection(
                title="Attrition Risk Summary",
                content=risk_content.strip(),
                confidence_band=conf_band,
                confidence_score=governed_confidence,
                section_type="insight",
                caveats=[
                    "Predicted rates are model estimates, not deterministic outcomes.",
                    "Individual predictions require human validation before any HR action.",
                ],
            ))

        # — Key Drivers —
        if top_features:
            drivers_content = ""
            for i, feat in enumerate(top_features[:8], 1):
                name = feat.get("feature_name", "?")
                imp  = feat.get("importance_score", 0.0)
                direction = feat.get("direction", "neutral")
                plain = feat.get("plain_english", "")
                arrow = "↑ associated with elevated predicted risk" if "increase" in direction else "↓ associated with lower predicted risk" if "decrease" in direction else "→ association direction unclear"
                drivers_content += f"  {i:2}. {name:<35} {imp:.4f}  {arrow}\n"
                if plain:
                    drivers_content += f"      {plain}\n"
            sections.append(ReportSection(
                title="Top Predictive Drivers",
                content=drivers_content.strip(),
                confidence_band=conf_band,
                confidence_score=governed_confidence * 0.95,
                section_type="insight",
            ))

        # — Ethical Governance —
        ethics_content = (
            f"Bias risk level : {bias_risk_level.upper()}\n"
            f"Ethical status  : {'PASS' if bias_risk_level in ('acceptable','low') else 'REVIEW REQUIRED'}\n\n"
            f"{ethical_disclaimer}"
        )
        ethics_caveats = []
        if bias_risk_level in {"critical", "high"}:
            ethics_caveats.append("Do NOT use predictions for personnel decisions without ethics review.")
        sections.append(ReportSection(
            title="Ethical Governance",
            content=ethics_content,
            confidence_band="N/A",
            confidence_score=1.0,
            section_type="disclaimer" if bias_risk_level in {"critical", "high"} else "metric",
            caveats=ethics_caveats,
        ))

        # — Scientific Validity & Model Integrity —
        _orig_auc_str = f"{original_auc:.4f}" if original_auc is not None else "N/A"
        _gov_auc_str  = f"{governed_auc:.4f}" if governed_auc is not None else f"{auc_score:.4f}"
        _mr_str       = f"{model_reliability_score:.0%}" if model_reliability_score is not None else "N/A"
        _brier_str    = f"{brier_score:.4f}" if brier_score is not None else "Not Evaluated"
        _ece_str      = f"{calibration_ece:.4f}" if calibration_ece is not None else "Not Evaluated"

        # Deployment verdict
        if leakage_n_critical > 0:
            _deploy_verdict = "NOT SAFE — Critical leakage detected. Do not use for decisions."
        elif leakage_risk_score > 0.40:
            _deploy_verdict = "CAUTION — Elevated leakage risk. Human validation required."
        elif calibration_quality_label in ("Poor",):
            _deploy_verdict = "CAUTION — Poor probability calibration. Risk scores should not be used as literal probabilities."
        elif model_reliability_score is not None and model_reliability_score < 0.60:
            _deploy_verdict = "LIMITED — Low model reliability. Use as preliminary indicator only."
        elif governed_confidence >= 0.75:
            _deploy_verdict = "SUITABLE for executive review with standard HR oversight protocols."
        else:
            _deploy_verdict = "MODERATE — Suitable for decision support with HR professional validation."

        sci_val_content = (
            f"Original AUC (raw)      : {_orig_auc_str}\n"
            f"Governed AUC            : {_gov_auc_str}\n"
            f"Model Reliability Score : {_mr_str}  (composite — not AUC-only)\n"
            f"Leakage Risk Score      : {leakage_risk_score:.3f}  "
            f"(critical flags: {leakage_n_critical}, high flags: {leakage_n_high})\n"
            f"Calibration Quality     : {calibration_quality_label}\n"
            f"Brier Score             : {_brier_str}  (0=perfect, 0.25=random)\n"
            f"Expected Calib. Error   : {_ece_str}\n"
            f"Deployment Verdict      : {_deploy_verdict}"
        )
        sci_val_caveats = []
        if leakage_n_critical > 0:
            sci_val_caveats.append(f"CRITICAL: {leakage_n_critical} leakage flag(s) detected — model reliability is significantly degraded.")
        if calibration_quality_label in ("Poor", "Not Evaluated"):
            sci_val_caveats.append(f"Calibration quality is {calibration_quality_label} — probability outputs may not reflect true risk levels.")

        _sci_band = (
            "Low" if leakage_n_critical > 0
            else "Moderate" if leakage_risk_score > 0.20 or calibration_quality_label == "Poor"
            else "High"
        )
        sections.append(ReportSection(
            title="Scientific Validity & Model Integrity",
            content=sci_val_content,
            confidence_band=_sci_band,
            confidence_score=model_reliability_score or governed_confidence,
            section_type="metric",
            caveats=sci_val_caveats,
        ))

        # — Provenance —
        prov_content = "Data lineage:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(provenance_steps))
        sections.append(ReportSection(
            title="Provenance Trace",
            content=prov_content,
            confidence_band="N/A",
            confidence_score=1.0,
            section_type="metric",
        ))

        # Assemble
        key_findings = self._extract_hr_findings(
            attrition_rate, top_features, auc_score, data_quality_score, bias_risk_level
        )
        risk_flags = []
        if bias_risk_level in {"critical", "high"}:
            risk_flags.append(f"Bias risk: {bias_risk_level.upper()} — fairness audit failed.")
        if auc_score < 0.65:
            risk_flags.append(f"Model AUC {auc_score:.3f} below acceptable threshold.")
        if data_quality_score < 0.55:
            risk_flags.append(f"Data quality {data_quality_score:.0%} — results may be unreliable.")

        recs = self._generate_hr_recommendations(
            auc_score, data_quality_score, bias_risk_level, attrition_rate
        )
        ethical_notes = [ethical_disclaimer] if ethical_disclaimer else []

        methodology = (
            f"Analysis performed using AutoML pipeline with {model_type} as the best model. "
            f"Training mode: {training_mode}. "
            "SMOTE oversampling applied inside cross-validation folds only. "
            "Feature engineering applied before model training. "
            "Confidence scores are governed (adjusted) estimates, not raw model probabilities."
        )
        quality_summary = (
            f"Data quality score: {data_quality_score:.0%} ({quality_desc}). "
            f"Dataset: {n_rows:,} records × {n_features} features. "
            + ("Target column present — supervised learning enabled." if target_column
               else "No target column — supervised learning not available.")
        )
        prov_summary = " → ".join(provenance_steps[:5]) if provenance_steps else "Standard pipeline."

        full_text = self._render_hr_text(
            generated_at, dataset_type, dataset_subtype, sections,
            key_findings, risk_flags, recs
        )
        html_text = self._render_hr_html(
            generated_at, dataset_type, dataset_subtype, sections,
            key_findings, risk_flags, recs, currency=currency,
        )

        return ExecutiveReport(
            report_title=f"Workforce Intelligence Report — {dataset_subtype}",
            dataset_type=dataset_type,
            dataset_subtype=dataset_subtype,
            generated_at=generated_at,
            overall_confidence=conf_band,
            overall_confidence_score=governed_confidence,
            sections=sections,
            key_findings=key_findings,
            risk_flags=risk_flags,
            ethical_notes=ethical_notes,
            recommendations=recs,
            methodology_note=methodology,
            currency=currency,
            platform_version=PLATFORM_VERSION,
            report_version=REPORT_VERSION,
            data_quality_summary=quality_summary,
            provenance_summary=prov_summary,
            full_text=full_text,
            html_text=html_text,
        )

    def generate_biosignal_report(
        self,
        *,
        signal_type: str,
        n_samples: int,
        n_windows: int,
        quality_score: float,
        stress_score: float,
        fatigue_score: float,
        anomaly_count: int,
        anomaly_pct: float,
        volatility_mean: float,
        top_features: List[Dict[str, Any]],
        disclaimer: str,
    ) -> ExecutiveReport:

        generated_at = _now_str()
        quality_band = _confidence_label(quality_score)

        sections: List[ReportSection] = []

        # Signal overview
        quality_desc = (
            "Excellent" if quality_score >= 0.85 else
            "Good"      if quality_score >= 0.70 else
            "Fair"      if quality_score >= 0.55 else
            "Poor"
        )
        overview = (
            f"Signal type    : {signal_type}\n"
            f"Signal samples : {n_samples:,}\n"
            f"Windows        : {n_windows}\n"
            f"Signal quality : {quality_desc} ({quality_score:.0%})\n"
            f"Analysis date  : {generated_at}"
        )
        sections.append(ReportSection(
            title="Signal Overview",
            content=overview,
            confidence_band="N/A",
            confidence_score=1.0,
            section_type="metric",
        ))

        # Composite Scores
        def stress_label(s):
            return "High" if s >= 0.70 else "Moderate" if s >= 0.40 else "Low"

        scores_content = (
            f"Stress Signal Score      : {stress_score:.3f} ({stress_label(stress_score)} stress)\n"
            f"Fatigue Signal Score     : {fatigue_score:.3f} ({stress_label(fatigue_score)} fatigue)\n"
            f"Volatility (mean)        : {volatility_mean:.3f}\n"
            f"Anomalous windows        : {anomaly_count} ({anomaly_pct:.1%} of windows)"
        )
        sections.append(ReportSection(
            title="Physiological Composite Scores",
            content=scores_content,
            confidence_band=quality_band,
            confidence_score=quality_score,
            section_type="insight",
            caveats=[
                "Scores are derived from signal processing algorithms, not clinical diagnostics.",
                "Results require validation by a qualified healthcare professional.",
            ],
        ))

        # Top signal features
        if top_features:
            feat_content = ""
            for i, f in enumerate(top_features[:6], 1):
                feat_content += f"  {i}. {f.get('feature_name','?'):<40} {f.get('plain_english','')}\n"
            sections.append(ReportSection(
                title="Key Signal Features",
                content=feat_content.strip(),
                confidence_band=quality_band,
                confidence_score=quality_score,
                section_type="insight",
            ))

        # Non-clinical disclaimer
        sections.append(ReportSection(
            title="Non-Clinical Disclaimer",
            content=disclaimer,
            confidence_band="N/A",
            confidence_score=1.0,
            section_type="disclaimer",
        ))

        key_findings = [
            f"Signal type: {signal_type} — {n_samples:,} samples processed across {n_windows} windows.",
            f"Stress Signal Score: {stress_score:.3f} — {stress_label(stress_score)} physiological stress pattern.",
            f"Anomalous windows: {anomaly_count} ({anomaly_pct:.1%}).",
            f"Signal quality: {quality_desc} ({quality_score:.0%}).",
        ]
        risk_flags = []
        if anomaly_pct > 0.20:
            risk_flags.append(f"High anomaly rate ({anomaly_pct:.1%}) — signal may require expert review.")
        if quality_score < 0.55:
            risk_flags.append(f"Signal quality below acceptable threshold ({quality_score:.0%}).")

        recs = [
            "Cross-reference findings with self-reported stress measures.",
            "Replicate analysis with additional signal modalities (HR, EDA, BVP).",
            "Consult a qualified physiologist or healthcare professional for clinical interpretation.",
        ]

        full_text = self._render_biosignal_text(
            generated_at, signal_type, sections, key_findings, risk_flags
        )

        return ExecutiveReport(
            report_title=f"Biosignal Stress Intelligence Report — {signal_type}",
            dataset_type="biosignal_timeseries",
            dataset_subtype=signal_type,
            generated_at=generated_at,
            overall_confidence=quality_band,
            overall_confidence_score=quality_score,
            sections=sections,
            key_findings=key_findings,
            risk_flags=risk_flags,
            ethical_notes=[disclaimer],
            recommendations=recs,
            methodology_note=(
                "Signal processed using 30-second windows with 50% overlap. "
                "Composite scores derived from domain-specific signal features. "
                "No clinical diagnostic claims are made."
            ),
            data_quality_summary=f"Signal quality: {quality_desc} ({quality_score:.0%}). {n_samples:,} samples, {n_windows} windows.",
            provenance_summary=f"Raw {signal_type} signal → windowing → feature extraction → scoring.",
            full_text=full_text,
        )

    def generate_profiling_report(
        self,
        *,
        dataset_type: str,
        n_rows: int,
        n_cols: int,
        data_quality_score: float,
        column_types: Dict[str, str],
        missing_pct: float,
        numeric_summary: Optional[Dict[str, Any]] = None,
    ) -> ExecutiveReport:
        generated_at = _now_str()
        quality_desc = (
            "Excellent" if data_quality_score >= 0.85 else
            "Good"      if data_quality_score >= 0.70 else
            "Fair"      if data_quality_score >= 0.55 else
            "Poor"
        )
        sections: List[ReportSection] = []

        overview = (
            f"Dataset type   : {dataset_type}\n"
            f"Rows           : {n_rows:,}\n"
            f"Columns        : {n_cols}\n"
            f"Missing values : {missing_pct:.1%} overall\n"
            f"Data quality   : {quality_desc} ({data_quality_score:.0%})\n"
            f"Analysis date  : {generated_at}"
        )
        sections.append(ReportSection(
            title="Dataset Profile",
            content=overview,
            confidence_band="N/A",
            confidence_score=1.0,
            section_type="metric",
        ))

        if column_types:
            type_summary = "\n".join(
                f"  {col:<35} {dtype}" for col, dtype in list(column_types.items())[:20]
            )
            sections.append(ReportSection(
                title="Column Types (first 20)",
                content=type_summary,
                confidence_band="N/A",
                confidence_score=1.0,
                section_type="metric",
            ))

        key_findings = [
            f"Unknown dataset type — profiling mode only.",
            f"{n_rows:,} rows × {n_cols} columns.",
            f"Missing data: {missing_pct:.1%}.",
            f"Data quality: {quality_desc}.",
        ]
        full_text = self._render_profiling_text(generated_at, dataset_type, sections, key_findings)

        return ExecutiveReport(
            report_title=f"Dataset Profiling Report — {dataset_type}",
            dataset_type=dataset_type,
            dataset_subtype="unknown",
            generated_at=generated_at,
            overall_confidence="N/A",
            overall_confidence_score=1.0,
            sections=sections,
            key_findings=key_findings,
            risk_flags=[],
            ethical_notes=["Dataset type could not be determined. Only structural profiling is presented."],
            recommendations=["Upload a labelled HR or biosignal dataset for full analysis."],
            methodology_note="Structural profiling only. No predictive modelling applied.",
            data_quality_summary=f"Quality: {quality_desc} ({data_quality_score:.0%}). {missing_pct:.1%} missing values.",
            provenance_summary="Raw file → profiler → column type detection → summary statistics.",
            full_text=full_text,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _extract_hr_findings(
        self, attrition_rate, top_features, auc, quality, bias_risk
    ) -> List[str]:
        findings = []
        if attrition_rate is not None:
            level = "elevated" if attrition_rate > 0.20 else "moderate" if attrition_rate > 0.10 else "low"
            findings.append(
                f"Predicted attrition rate: {_fmt_pct(attrition_rate)} ({level} predicted risk — "
                f"for HR review and human validation, not automated action)."
            )
        if top_features:
            top = top_features[0]
            findings.append(
                f"Top statistical driver: '{top.get('feature_name','?')}' shows the strongest "
                f"association with predicted risk in this dataset (importance: {top.get('importance_score',0):.4f}). "
                f"This is a statistical association, not a causal claim."
            )
        findings.append(f"Model AUC-ROC: {auc:.4f} (governed estimate).")
        if bias_risk in {"critical", "high"}:
            findings.append(
                f"FAIRNESS ALERT: {bias_risk.upper()} bias risk detected. "
                "Expert review required before use in any HR context."
            )
        return findings

    def _generate_hr_recommendations(
        self, auc, quality, bias_risk, attrition_rate
    ) -> List[str]:
        recs = []
        if attrition_rate and attrition_rate > 0.20:
            recs.append(
                "High predicted attrition rate signals a priority segment for structured "
                "HR review and retention-focused conversations. Human validation required."
            )
        if auc < 0.75:
            recs.append(
                "Model accuracy is moderate. Collect additional data and re-validate "
                "before using predictions to inform strategic workforce decisions."
            )
        if quality < 0.70:
            recs.append(
                "Improve data completeness — address missing values and inconsistent records "
                "to increase analytical reliability."
            )
        if bias_risk in {"critical", "high"}:
            recs.append(
                "Engage HR ethics and legal review before referencing predictions "
                "in any employment-related decision process."
            )
        if not recs:
            recs.append(
                "Continue scheduled monitoring. Re-train model quarterly or when "
                "workforce composition changes by more than 10%."
            )
        return recs

    def _render_hr_text(
        self, generated_at, dtype, subtype, sections, findings, risks, recs
    ) -> str:
        lines = [
            "=" * 72,
            f"  {PLATFORM_NAME}",
            f"  WORKFORCE INTELLIGENCE REPORT  (v{REPORT_VERSION})",
            f"  Dataset: {dtype} / {subtype}",
            f"  Generated: {generated_at}",
            "=" * 72,
            "",
            "IMPORTANT NOTICE",
            "-" * 40,
            "  " + HUMAN_OVERSIGHT_DISCLAIMER,
            "",
            "KEY FINDINGS",
            "-" * 40,
        ]
        for f in findings:
            lines.append(f"  • {f}")
        if risks:
            lines += ["", "RISK FLAGS", "-" * 40]
            for r in risks:
                lines.append(f"  ! {r}")
        lines += ["", "ANALYSIS SECTIONS", "-" * 40]
        for s in sections:
            lines += [
                "",
                f"  [{s.section_type.upper()}] {s.title}  {_conf_badge(s.confidence_band)}",
                "",
            ]
            for line in s.content.splitlines():
                lines.append(f"    {line}")
            if s.caveats:
                lines.append("")
                for c in s.caveats:
                    lines.append(f"    NOTE: {c}")
        lines += ["", "RECOMMENDATIONS", "-" * 40]
        for r in recs:
            lines.append(f"  - {r}")
        lines += [
            "",
            "LIMITATIONS",
            "-" * 40,
            "  • Predictions are probabilistic estimates, not certainties.",
            "  • Results are dataset-specific and may not generalise to future cohorts.",
            "  • Human judgment is required before any workforce action is taken.",
            "",
            "=" * 72,
            f"  {PLATFORM_NAME} v{PLATFORM_VERSION}",
            "=" * 72,
        ]
        return "\n".join(lines)

    def _render_hr_html(
        self, generated_at, dtype, subtype, sections, findings, risks, recs,
        currency: str = DEFAULT_CURRENCY,
    ) -> str:
        sym = CURRENCY_SYMBOLS.get(currency, currency)
        esc = _html_escape.escape

        def badge(band: str) -> str:
            colors = {
                "High": ("#16a34a", "#f0fdf4"), "Moderate": ("#d97706", "#fffbeb"),
                "Low": ("#ea580c", "#fff7ed"), "Unreliable": ("#dc2626", "#fef2f2"),
                "N/A": ("#6b7280", "#f9fafb"),
            }
            c, bg = colors.get(band, ("#6b7280", "#f9fafb"))
            return (f'<span style="background:{bg};color:{c};border:1px solid {c};'
                    f'border-radius:3px;padding:1px 6px;font-size:0.78rem;font-weight:700">'
                    f'{esc(band)}</span>')

        parts = [
            '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">',
            f'<title>Workforce Intelligence Report</title>',
            '<style>',
            'body{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#1f2937}',
            'h1{color:#1e3a8a;border-bottom:3px solid #3b82f6;padding-bottom:8px}',
            'h2{color:#1e40af;margin-top:32px;border-bottom:1px solid #bfdbfe;padding-bottom:4px}',
            '.meta{color:#6b7280;font-size:0.85rem;margin-bottom:24px}',
            '.disclaimer{background:#fef2f2;border-left:4px solid #dc2626;padding:12px 16px;',
            '  border-radius:4px;margin:16px 0;font-size:0.9rem}',
            '.finding{padding:4px 0;border-bottom:1px solid #f3f4f6}',
            '.risk{background:#fff7ed;border-left:4px solid #ea580c;padding:8px 12px;',
            '  border-radius:4px;margin:8px 0;font-size:0.9rem}',
            '.section-box{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;',
            '  padding:16px;margin:16px 0}',
            '.caveat{color:#92400e;font-size:0.83rem;margin-top:8px}',
            '.rec{padding:6px 0;border-bottom:1px solid #f3f4f6}',
            '.footer{color:#9ca3af;font-size:0.78rem;margin-top:40px;border-top:1px solid #e5e7eb;',
            '  padding-top:12px}',
            'pre{background:#f9fafb;padding:12px;border-radius:4px;font-size:0.85rem;',
            '  white-space:pre-wrap;word-break:break-word}',
            '</style></head><body>',
            f'<h1>Workforce Intelligence Report</h1>',
            f'<div class="meta">{esc(PLATFORM_NAME)} v{esc(PLATFORM_VERSION)} &nbsp;|&nbsp;',
            f'Report v{esc(REPORT_VERSION)} &nbsp;|&nbsp; Generated: {esc(generated_at)}<br>',
            f'Dataset: {esc(dtype)} / {esc(subtype)} &nbsp;|&nbsp; Currency: {esc(sym)}</div>',
            '<div class="disclaimer">',
            f'<strong>Important:</strong> {esc(HUMAN_OVERSIGHT_DISCLAIMER)}',
            '</div>',
            '<h2>Key Findings</h2><ul>',
        ]
        for f in findings:
            parts.append(f'<li class="finding">{esc(f)}</li>')
        parts.append('</ul>')

        if risks:
            parts.append('<h2>Risk Flags</h2>')
            for r in risks:
                parts.append(f'<div class="risk">{esc(r)}</div>')

        parts.append('<h2>Analysis Sections</h2>')
        for s in sections:
            conf_badge = badge(s.confidence_band)
            parts += [
                '<div class="section-box">',
                f'<strong>{esc(s.title)}</strong> {conf_badge}',
                f'<pre>{esc(s.content)}</pre>',
            ]
            for c in s.caveats:
                parts.append(f'<div class="caveat">Note: {esc(c)}</div>')
            parts.append('</div>')

        parts.append('<h2>Recommendations</h2><ol>')
        for r in recs:
            parts.append(f'<li class="rec">{esc(r)}</li>')
        parts.append('</ol>')

        parts += [
            '<h2>Limitations</h2><ul>',
            '<li>Predictions are probabilistic estimates, not certainties.</li>',
            '<li>Results are dataset-specific and may not generalise to future cohorts.</li>',
            '<li>Human judgment is required before any workforce action is taken.</li>',
            '</ul>',
            f'<div class="footer">{esc(PLATFORM_NAME)} v{esc(PLATFORM_VERSION)} | '
            f'Report v{esc(REPORT_VERSION)} | {esc(generated_at)}</div>',
            '</body></html>',
        ]
        return "\n".join(parts)

    def _render_biosignal_text(
        self, generated_at, signal_type, sections, findings, risks
    ) -> str:
        lines = [
            "=" * 72,
            f"  BIOSIGNAL STRESS INTELLIGENCE REPORT — {signal_type}",
            f"  Generated: {generated_at}",
            "=" * 72,
            "",
            "KEY FINDINGS",
            "-" * 40,
        ]
        for f in findings:
            lines.append(f"  • {f}")
        if risks:
            lines += ["", "RISK FLAGS", "-" * 40]
            for r in risks:
                lines.append(f"  ⚠ {r}")
        lines += ["", "ANALYSIS SECTIONS", "-" * 40]
        for s in sections:
            lines += ["", f"  {s.title}", "  " + "-" * 36]
            for line in s.content.splitlines():
                lines.append(f"    {line}")
        lines += ["", "=" * 72]
        return "\n".join(lines)

    def _render_profiling_text(
        self, generated_at, dtype, sections, findings
    ) -> str:
        lines = [
            "=" * 72,
            f"  DATASET PROFILING REPORT — {dtype}",
            f"  Generated: {generated_at}",
            "=" * 72,
            "",
            "SUMMARY",
            "-" * 40,
        ]
        for f in findings:
            lines.append(f"  • {f}")
        lines += ["", "PROFILE DETAILS", "-" * 40]
        for s in sections:
            lines += ["", f"  {s.title}", "  " + "-" * 36]
            for line in s.content.splitlines():
                lines.append(f"    {line}")
        lines += ["", "=" * 72]
        return "\n".join(lines)
