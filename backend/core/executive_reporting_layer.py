"""
Executive Reporting Layer — Phase 6.

Produces governance-safe, language-audited executive summaries for HR
leadership. All output text is routed through EnterpriseLanguageGuard
before being returned. No individual employee identification. No
deterministic predictions. No causal language.

Design constraints:
  - No individual employee risk scores in report narratives
  - All risk language uses probabilistic framing
  - All generated text passes EnterpriseLanguageGuard.is_compliant()
  - Department-level analysis only — no sub-department individual targeting
  - Recommendations are intervention-category suggestions, not directives
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.enterprise_language_guard import EnterpriseLanguageGuard

# Risk band thresholds (probability)
_LOW_RISK_MAX = 0.30
_HIGH_RISK_MIN = 0.60

# Workforce volatility thresholds (fraction of workforce in high-risk band)
_VOLATILITY_ELEVATED_MIN = 0.15
_VOLATILITY_HIGH_MIN = 0.30
_VOLATILITY_CRITICAL_MIN = 0.45

# Department reliability minimum size
_DEPT_MIN_RELIABLE = 10

# Volatility labels
VOLATILITY_LOW = "LOW"
VOLATILITY_ELEVATED = "ELEVATED"
VOLATILITY_HIGH = "HIGH"
VOLATILITY_CRITICAL = "CRITICAL"

# Overall report reliability labels
RELIABILITY_RELIABLE = "RELIABLE"
RELIABILITY_UNRELIABLE = "UNRELIABLE"
RELIABILITY_CRITICAL = "CRITICAL"
RELIABILITY_NOT_EVALUATED = "NOT_EVALUATED"


@dataclass
class DepartmentRiskSummary:
    """
    Department-level aggregate risk summary.

    Contains no individual employee data. All figures are population-level
    aggregates suitable for executive consumption.
    """
    department: str
    n_employees: int
    mean_risk_score: float
    risk_band: str  # LOW / MEDIUM / HIGH
    fraction_high_risk: float
    is_reliable: bool
    reliability_note: str
    recommended_action_category: str  # governance-safe intervention category


@dataclass
class OrganizationRiskSummary:
    """Workforce-level aggregate metrics."""
    n_employees_total: int
    fraction_low_risk: float
    fraction_medium_risk: float
    fraction_high_risk: float
    mean_risk_score: float
    workforce_volatility_indicator: str  # LOW / ELEVATED / HIGH / CRITICAL
    high_risk_concentration_flag: bool


@dataclass
class ExecutiveReport:
    """
    Governance-safe executive intelligence report.

    Generated text has been audited by EnterpriseLanguageGuard.
    No individual employee data. No deterministic predictions.
    """
    generated_at: str
    organization_summary: OrganizationRiskSummary
    department_summaries: list[DepartmentRiskSummary] = field(default_factory=list)
    intervention_recommendation_categories: list[str] = field(default_factory=list)
    confidence_reliability: str = RELIABILITY_NOT_EVALUATED
    high_risk_concentration_alert: Optional[str] = None
    language_compliant: bool = True
    language_violations_detected: int = 0
    governance_notes: list[str] = field(default_factory=list)
    executive_narrative: str = ""
    summary: str = ""


class ExecutiveReportingLayer:
    """
    Produces governance-safe executive reports from model predictions.

    All text generation routes through EnterpriseLanguageGuard.
    Stateless: each call to generate() is independent.
    """

    def __init__(self) -> None:
        self._guard = EnterpriseLanguageGuard()

    def generate(
        self,
        df: pd.DataFrame,
        y_prob: pd.Series,
        department_col: Optional[str] = None,
        calibration_reliability: str = RELIABILITY_NOT_EVALUATED,
        fold_auc_std: Optional[float] = None,
    ) -> ExecutiveReport:
        """
        Generate an executive-level workforce risk intelligence report.

        Parameters
        ----------
        df : pd.DataFrame
            Workforce dataset. Must NOT contain individual PII fields.
        y_prob : pd.Series
            Predicted attrition probabilities. Must be aligned with df index.
        department_col : str, optional
            Column name for department grouping.
        calibration_reliability : str
            Overall reliability rating from CalibrationReliabilityAuditor.
        fold_auc_std : float, optional
            Cross-fold AUC standard deviation (for confidence note).
        """
        generated_at = datetime.datetime.utcnow().isoformat() + "Z"
        governance_notes: list[str] = []
        language_violations = 0

        # ── Organization-level summary ─────────────────────────────────────
        n_total = len(y_prob)
        n_low = int((y_prob < _LOW_RISK_MAX).sum())
        n_high = int((y_prob >= _HIGH_RISK_MIN).sum())
        n_medium = n_total - n_low - n_high

        frac_low = n_low / n_total if n_total > 0 else 0.0
        frac_medium = n_medium / n_total if n_total > 0 else 0.0
        frac_high = n_high / n_total if n_total > 0 else 0.0
        mean_score = float(y_prob.mean()) if n_total > 0 else 0.0

        volatility = self._compute_volatility(frac_high)
        concentration_flag = frac_high > 0.40

        org_summary = OrganizationRiskSummary(
            n_employees_total=n_total,
            fraction_low_risk=round(frac_low, 3),
            fraction_medium_risk=round(frac_medium, 3),
            fraction_high_risk=round(frac_high, 3),
            mean_risk_score=round(mean_score, 3),
            workforce_volatility_indicator=volatility,
            high_risk_concentration_flag=concentration_flag,
        )

        # ── Department summaries ───────────────────────────────────────────
        dept_summaries: list[DepartmentRiskSummary] = []
        if department_col and department_col in df.columns:
            dept_summaries = self._build_department_summaries(df, y_prob, department_col)

        # ── Concentration alert (governance-safe text) ─────────────────────
        concentration_alert = None
        if concentration_flag:
            alert_text = (
                f"Workforce risk concentration is elevated: {frac_high:.1%} of employees "
                "show high-risk attrition indicators. When more than 40% of the workforce "
                "is in the high-risk band, model discrimination may be limited. "
                "HR leadership review of calibration is recommended before planning interventions."
            )
            audit = self._guard.audit(alert_text)
            if not audit.is_compliant:
                language_violations += audit.n_critical + audit.n_high
                alert_text = audit.safe_text
                governance_notes.append("Concentration alert text was modified by language guard.")
            concentration_alert = alert_text

        # ── Intervention recommendation categories ─────────────────────────
        recommendations = self._generate_recommendations(
            volatility, frac_high, dept_summaries, governance_notes
        )

        # ── Executive narrative (language-guarded) ─────────────────────────
        narrative = self._generate_narrative(
            org_summary, volatility, calibration_reliability, fold_auc_std
        )
        narrative_audit = self._guard.audit(narrative)
        if not narrative_audit.is_compliant:
            language_violations += narrative_audit.n_critical + narrative_audit.n_high
            narrative = narrative_audit.safe_text
            governance_notes.append(
                f"Executive narrative required {narrative_audit.n_critical + narrative_audit.n_high} "
                "language corrections by EnterpriseLanguageGuard."
            )

        # ── Reliability note ───────────────────────────────────────────────
        if calibration_reliability == RELIABILITY_CRITICAL:
            governance_notes.append(
                "CRITICAL: Model calibration reliability is CRITICAL. "
                "This report must NOT be used for HR decisions until calibration is reviewed."
            )
        elif calibration_reliability == RELIABILITY_UNRELIABLE:
            governance_notes.append(
                "Model calibration reliability is UNRELIABLE. "
                "Treat all risk scores as indicative only. HR professional review required."
            )

        if fold_auc_std is not None and fold_auc_std > 0.08:
            governance_notes.append(
                f"Cross-fold AUC standard deviation ({fold_auc_std:.3f}) exceeds stability threshold (0.08). "
                "Model performance is inconsistent across data subsets."
            )

        governance_notes.append(
            "This report contains population-level aggregate statistics only. "
            "No individual employee data is included. Risk scores are probabilistic indicators, "
            "not determinations of individual employee intent or behavior."
        )

        summary = (
            f"Executive report generated at {generated_at}: "
            f"{n_total} employees assessed, "
            f"{frac_high:.1%} in high-risk band, "
            f"volatility={volatility}, "
            f"reliability={calibration_reliability}."
        )

        return ExecutiveReport(
            generated_at=generated_at,
            organization_summary=org_summary,
            department_summaries=dept_summaries,
            intervention_recommendation_categories=recommendations,
            confidence_reliability=calibration_reliability,
            high_risk_concentration_alert=concentration_alert,
            language_compliant=(language_violations == 0),
            language_violations_detected=language_violations,
            governance_notes=governance_notes,
            executive_narrative=narrative,
            summary=summary,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _compute_volatility(self, frac_high: float) -> str:
        if frac_high >= _VOLATILITY_CRITICAL_MIN:
            return VOLATILITY_CRITICAL
        if frac_high >= _VOLATILITY_HIGH_MIN:
            return VOLATILITY_HIGH
        if frac_high >= _VOLATILITY_ELEVATED_MIN:
            return VOLATILITY_ELEVATED
        return VOLATILITY_LOW

    def _build_department_summaries(
        self,
        df: pd.DataFrame,
        y_prob: pd.Series,
        department_col: str,
    ) -> list[DepartmentRiskSummary]:
        summaries = []
        depts = df[department_col].dropna().unique()

        for dept in depts:
            mask = df[department_col] == dept
            dept_prob = y_prob[mask]
            n_dept = int(mask.sum())
            mean_score = float(dept_prob.mean())
            frac_high = float((dept_prob >= _HIGH_RISK_MIN).mean())
            is_reliable = n_dept >= _DEPT_MIN_RELIABLE

            if mean_score >= _HIGH_RISK_MIN:
                risk_band = "HIGH"
            elif mean_score >= _LOW_RISK_MAX:
                risk_band = "MEDIUM"
            else:
                risk_band = "LOW"

            if not is_reliable:
                reliability_note = (
                    f"Team size ({n_dept}) is below the minimum threshold for reliable "
                    "statistical predictions. Use qualitative HR assessment for this team."
                )
            else:
                reliability_note = "Team size meets minimum threshold for statistical reliability."

            action = self._map_risk_to_action_category(risk_band, frac_high, is_reliable)

            summaries.append(DepartmentRiskSummary(
                department=dept,
                n_employees=n_dept,
                mean_risk_score=round(mean_score, 3),
                risk_band=risk_band,
                fraction_high_risk=round(frac_high, 3),
                is_reliable=is_reliable,
                reliability_note=reliability_note,
                recommended_action_category=action,
            ))

        summaries.sort(key=lambda s: s.mean_risk_score, reverse=True)
        return summaries

    def _map_risk_to_action_category(
        self, risk_band: str, frac_high: float, is_reliable: bool
    ) -> str:
        if not is_reliable:
            return "Qualitative HR Assessment Recommended — insufficient data for statistical analysis"
        if risk_band == "HIGH" or frac_high >= 0.40:
            return "Priority HR Engagement Review — elevated workforce risk indicators detected"
        if risk_band == "MEDIUM":
            return "Standard Retention Program Review — moderate risk indicators present"
        return "Routine Monitoring — low risk indicator profile"

    def _generate_recommendations(
        self,
        volatility: str,
        frac_high: float,
        dept_summaries: list[DepartmentRiskSummary],
        governance_notes: list[str],
    ) -> list[str]:
        recommendations: list[str] = []

        if volatility in (VOLATILITY_HIGH, VOLATILITY_CRITICAL):
            recommendations.append(
                "Workforce-wide engagement review: elevated risk indicators across the organization "
                "suggest a systemic pattern. HR leadership review of organizational factors is recommended."
            )
        elif volatility == VOLATILITY_ELEVATED:
            recommendations.append(
                "Targeted department review: risk indicators are elevated in specific organizational units. "
                "Focus retention programs on the highest-risk departments."
            )
        else:
            recommendations.append(
                "Routine monitoring: workforce risk indicators are within expected range. "
                "Continue standard HR engagement practices."
            )

        high_risk_depts = [
            s for s in dept_summaries
            if s.risk_band == "HIGH" and s.is_reliable
        ]
        if high_risk_depts:
            top_dept = high_risk_depts[0].department
            recommendations.append(
                f"Priority department engagement review recommended for teams showing elevated "
                "risk indicators. HR business partners should assess engagement factors, workload "
                "sustainability, and career development pathways."
            )

        unreliable_depts = [s for s in dept_summaries if not s.is_reliable]
        if unreliable_depts:
            recommendations.append(
                f"{len(unreliable_depts)} organizational unit(s) are below the minimum size for "
                "reliable statistical analysis. Qualitative HR assessment is recommended for these teams."
            )

        recommendations.append(
            "All retention interventions should be designed and executed by qualified HR professionals. "
            "Statistical risk indicators are one input to HR decision-making, not a standalone directive."
        )

        # Audit all recommendation text
        for i, rec in enumerate(recommendations):
            audit = self._guard.audit(rec)
            if not audit.is_compliant:
                recommendations[i] = audit.safe_text
                governance_notes.append(f"Recommendation #{i+1} text was modified by language guard.")

        return recommendations

    def _generate_narrative(
        self,
        org_summary: OrganizationRiskSummary,
        volatility: str,
        calibration_reliability: str,
        fold_auc_std: Optional[float],
    ) -> str:
        frac_high_pct = f"{org_summary.fraction_high_risk:.1%}"
        frac_low_pct = f"{org_summary.fraction_low_risk:.1%}"

        volatility_text = {
            VOLATILITY_LOW: "within expected norms",
            VOLATILITY_ELEVATED: "moderately elevated",
            VOLATILITY_HIGH: "substantially elevated",
            VOLATILITY_CRITICAL: "at a critical level requiring immediate HR leadership attention",
        }.get(volatility, "at an uncertain level")

        reliability_text = {
            RELIABILITY_RELIABLE: "The model's predictions are considered statistically reliable for this dataset.",
            RELIABILITY_UNRELIABLE: "Model reliability is below acceptable thresholds. Treat all risk indicators as preliminary.",
            RELIABILITY_CRITICAL: "IMPORTANT: Model reliability is critically low. This report must not inform HR decisions until model issues are resolved.",
            RELIABILITY_NOT_EVALUATED: "Model reliability has not been evaluated. Treat all risk indicators with appropriate caution.",
        }.get(calibration_reliability, "Model reliability status is unknown.")

        stability_text = ""
        if fold_auc_std is not None:
            if fold_auc_std > 0.12:
                stability_text = " Cross-validation stability is critically low — the model performs inconsistently across data subsets."
            elif fold_auc_std > 0.08:
                stability_text = " Cross-validation stability shows moderate variability — monitor performance across different employee groups."
            else:
                stability_text = " Cross-validation stability is acceptable."

        narrative = (
            f"Workforce Risk Intelligence Summary: This assessment covers {org_summary.n_employees_total} employees. "
            f"Attrition risk indicators are {volatility_text}. "
            f"{frac_high_pct} of employees show elevated risk indicators, while "
            f"{frac_low_pct} show low risk indicators. "
            f"The mean workforce risk score is {org_summary.mean_risk_score:.2f} (scale 0–1). "
            f"{reliability_text}"
            f"{stability_text} "
            "Risk scores are probabilistic indicators derived from organizational patterns in HR data. "
            "They do not represent determinations of individual employee intent. "
            "All risk-based HR actions must involve qualified HR professional review."
        )

        return narrative


def generate_executive_report(
    df: pd.DataFrame,
    y_prob: pd.Series,
    department_col: Optional[str] = None,
    calibration_reliability: str = RELIABILITY_NOT_EVALUATED,
    fold_auc_std: Optional[float] = None,
) -> ExecutiveReport:
    """Convenience function wrapping ExecutiveReportingLayer.generate()."""
    layer = ExecutiveReportingLayer()
    return layer.generate(
        df=df,
        y_prob=y_prob,
        department_col=department_col,
        calibration_reliability=calibration_reliability,
        fold_auc_std=fold_auc_std,
    )
