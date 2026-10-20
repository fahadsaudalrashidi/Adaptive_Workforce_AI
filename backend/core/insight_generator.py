"""
Insight Generator — Autonomous Natural-Language Insight Engine

Converts quantitative risk scores, model metrics, and dataset stats into
concise, action-oriented text insights. No LLM dependency — pure rule-based
and threshold-driven generation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from config.settings import MAX_INSIGHTS, INSIGHT_MIN_EFFECT_SIZE, CURRENCY_SYMBOLS
from .risk_intelligence import OrganizationalRisk, DepartmentRisk


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Insight:
    category: str           # "risk" / "opportunity" / "recommendation" / "warning"
    priority: int           # 1=highest, 3=lowest
    title: str
    body: str
    metric_context: Optional[str] = None
    action: Optional[str] = None


@dataclass
class InsightReport:
    dataset_type: str
    insights: List[Insight] = field(default_factory=list)
    executive_summary: str = ""
    risk_headline: str = ""
    recommended_actions_30d: List[str] = field(default_factory=list)
    recommended_actions_60d: List[str] = field(default_factory=list)
    recommended_actions_90d: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# HR / ATTRITION INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

def generate_hr_insights(org_risk: OrganizationalRisk,
                          model_auc: float = 0.0,
                          dept_risks: Optional[List[DepartmentRisk]] = None,
                          currency: Optional[str] = None) -> List[Insight]:
    insights: List[Insight] = []
    dept_risks = dept_risks or org_risk.department_risks
    _curr = currency or getattr(org_risk, "currency", "SAR")
    _curr_sym = CURRENCY_SYMBOLS.get(_curr, _curr)

    # Overall attrition risk
    risk_pct = org_risk.overall_attrition_risk * 100
    if risk_pct >= 65:
        insights.append(Insight(
            category="risk", priority=1,
            title="Critical Organisational Attrition Signal",
            body=f"Organisation-wide predicted attrition probability is {risk_pct:.1f}% — "
                 f"exceeding critical threshold. {org_risk.high_risk_employees} employees "
                 f"({org_risk.high_risk_pct:.0%}) are in the priority review segment. "
                 f"Human validation is required before any action.",
            metric_context=f"Avg attrition probability: {risk_pct:.1f}%",
            action="Convene HR leadership to review priority-segment employees — no automated action",
        ))
    elif risk_pct >= 45:
        insights.append(Insight(
            category="warning", priority=1,
            title="Elevated Workforce Attrition Signal",
            body=f"Predicted attrition probability ({risk_pct:.1f}%) has entered the elevated range. "
                 f"{org_risk.high_risk_employees} employees are flagged for structured HR review.",
            action="Schedule departmental retention reviews — HR validation required",
        ))

    # Financial exposure
    fin_val = org_risk.total_financial_exposure
    if fin_val > 0:
        insights.append(Insight(
            category="risk", priority=2,
            title="Financial Exposure from Projected Attrition",
            body=f"Estimated replacement cost exposure is {_curr_sym} {fin_val:,.0f} based on "
                 f"current risk profile and 50% salary replacement factor.",
            metric_context=f"Total exposure: {_curr_sym} {fin_val:,.0f}",
            action="Proactive retention investment typically costs 10–20% of replacement cost",
        ))

    # Most at-risk department
    if org_risk.most_at_risk_dept and dept_risks:
        top_dept = next((d for d in dept_risks
                         if d.department == org_risk.most_at_risk_dept), None)
        if top_dept:
            insights.append(Insight(
                category="risk", priority=1,
                title=f"High-Risk Department: {top_dept.department}",
                body=f"{top_dept.department} has the highest average attrition probability "
                     f"({top_dept.avg_attrition_prob:.1%}) with {top_dept.high_risk_count} "
                     f"high-risk employees out of {top_dept.n_employees}.",
                action=f"Prioritise {top_dept.department} for manager check-ins and retention interviews",
            ))

    # Burnout hotspot
    if org_risk.burnout_hotspot and org_risk.burnout_hotspot != org_risk.most_at_risk_dept:
        insights.append(Insight(
            category="warning", priority=2,
            title=f"Burnout Hotspot: {org_risk.burnout_hotspot}",
            body=f"{org_risk.burnout_hotspot} shows the highest average burnout risk score, "
                 f"indicating potential exhaustion from workload pressure or lack of resources.",
            action="Deploy workload audits and flexible-work options in this department",
        ))

    # Sustainability
    if org_risk.sustainability_score < 50:
        insights.append(Insight(
            category="warning", priority=2,
            title="Workforce Sustainability Below Threshold",
            body=f"Organisational sustainability score is {org_risk.sustainability_score:.0f}/100, "
                 f"driven by combined attrition risk and engagement deficit.",
            action="Implement Employee Value Proposition (EVP) refresh and engagement programmes",
        ))

    # Model quality note
    if model_auc > 0:
        if model_auc >= 0.80:
            insights.append(Insight(
                category="opportunity", priority=3,
                title="Predictive Model Available — Governance Review Recommended",
                body=f"The attrition prediction model achieved AUC={model_auc:.3f}. "
                     f"High AUC values on HR data warrant review of leakage and calibration "
                     f"reports before treating individual scores as reliable. "
                     f"All outputs require human validation.",
                metric_context=f"AUC: {model_auc:.3f}",
            ))
        elif model_auc < 0.65:
            insights.append(Insight(
                category="warning", priority=3,
                title="Limited Model Predictive Power",
                body=f"Model AUC={model_auc:.3f} suggests moderate discrimination. "
                     f"Scores should be interpreted as indicative, not definitive.",
                action="Collect more data or enrich with additional HR signals",
            ))

    return insights


# ─────────────────────────────────────────────────────────────────────────────
# BIOSIGNAL INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

def generate_biosignal_insights(signal_type: str,
                                  global_stats: Dict[str, float],
                                  stress_score: float,
                                  quality_score: float,
                                  anomaly_count: int) -> List[Insight]:
    insights: List[Insight] = []

    insights.append(Insight(
        category="recommendation", priority=3,
        title=f"Biosignal Dataset — {signal_type} Analysis",
        body=f"This dataset contains physiological sensor data ({signal_type}), not employee records. "
             f"Individual rows represent signal samples, not employees. "
             f"Attrition prediction is not applicable.",
        action="Use Stress/Fatigue Analysis and Physiological Instability dashboards",
    ))

    if stress_score >= 0.65:
        insights.append(Insight(
            category="risk", priority=1,
            title=f"Elevated Physiological Stress Signal ({signal_type})",
            body=f"Composite stress indicator is {stress_score:.0%} — above the high threshold. "
                 f"Signal statistics: mean={global_stats.get('mean', 0):.2f}, "
                 f"std={global_stats.get('std', 0):.2f}.",
            action="Review measurement context; check for confounding physical activity",
        ))

    if anomaly_count > 0:
        insights.append(Insight(
            category="warning", priority=2,
            title=f"{anomaly_count} Signal Anomalies Detected",
            body=f"{anomaly_count} z-score anomalies found in the {signal_type} signal. "
                 f"These may represent artefacts, measurement errors, or genuine physiological events.",
            action="Manual inspection of flagged windows recommended before clinical interpretation",
        ))

    if quality_score < 60:
        insights.append(Insight(
            category="warning", priority=2,
            title="Low Signal Quality",
            body=f"Signal quality score is {quality_score:.0f}/100. "
                 f"Missing data or out-of-range values detected.",
            action="Check sensor placement and data collection protocol",
        ))

    return insights


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC / UNKNOWN DATASET INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

def generate_generic_insights(quality_score: float,
                                n_rows: int,
                                n_cols: int,
                                missing_pct: float,
                                n_numeric: int,
                                n_categorical: int,
                                dataset_type: str = "unknown") -> List[Insight]:
    insights: List[Insight] = []

    insights.append(Insight(
        category="recommendation", priority=3,
        title=f"Dataset Intelligence Report — {dataset_type.replace('_', ' ').title()}",
        body=f"Loaded {n_rows:,} rows × {n_cols} columns. "
             f"{n_numeric} numeric, {n_categorical} categorical features. "
             f"Overall data quality: {quality_score:.0f}/100.",
    ))

    if missing_pct > 0.20:
        insights.append(Insight(
            category="warning", priority=2,
            title="High Missing Data Rate",
            body=f"{missing_pct:.0%} of values are missing across all columns. "
                 f"This may reduce model quality.",
            action="Review missing data imputation strategy; consider domain-specific fill values",
        ))

    if n_rows < 200:
        insights.append(Insight(
            category="warning", priority=2,
            title="Small Dataset — Limited ML Reliability",
            body=f"Only {n_rows} rows available. Machine learning estimates will have high variance. "
                 f"Consider collecting more data before deploying predictions.",
        ))

    return insights


# ─────────────────────────────────────────────────────────────────────────────
# ACTION PLAN GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_action_plan(org_risk: OrganizationalRisk) -> Dict[str, List[str]]:
    actions_30: List[str] = []
    actions_60: List[str] = []
    actions_90: List[str] = []

    rp = org_risk.overall_attrition_risk

    if rp >= 0.60:
        actions_30 += [
            "Identify top 10% highest-risk employees and schedule confidential stay interviews",
            f"Deploy emergency retention package for {org_risk.most_at_risk_dept or 'high-risk departments'}",
        ]
    if rp >= 0.40:
        actions_30.append("Launch pulse survey to surface undisclosed dissatisfaction drivers")
        actions_60 += [
            "Review compensation benchmarking against market rates",
            "Implement structured career-progression conversations for all high-risk employees",
        ]

    if org_risk.burnout_hotspot:
        actions_30.append(f"Conduct workload audit in {org_risk.burnout_hotspot}")
        actions_60.append(f"Introduce flexible-work trial in {org_risk.burnout_hotspot}")

    actions_60.append("Review manager effectiveness scores and provide targeted coaching")
    actions_90 += [
        "Evaluate impact of 30-day interventions via follow-up risk scoring",
        "Integrate risk model into regular HR reporting cycle (monthly refresh)",
        "Build EVP enhancement roadmap with HR and business leaders",
    ]

    return {"30_day": actions_30, "60_day": actions_60, "90_day": actions_90}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class InsightGenerator:
    """
    Generates an InsightReport from analysis results.

    Usage
    -----
    gen = InsightGenerator()
    report = gen.generate(org_risk, dataset_type, model_auc=0.79)
    """

    def generate(self,
                 dataset_type: str,
                 org_risk: Optional[OrganizationalRisk] = None,
                 model_auc: float = 0.0,
                 quality_score: float = 80.0,
                 n_rows: int = 0,
                 n_cols: int = 0,
                 missing_pct: float = 0.0,
                 n_numeric: int = 0,
                 n_categorical: int = 0,
                 biosignal_context: Optional[Dict] = None,
                 currency: Optional[str] = None) -> InsightReport:

        all_insights: List[Insight] = []

        _curr = currency or getattr(org_risk, "currency", None) or "SAR"
        if dataset_type in ("hr_attrition", "hr_engagement", "hr_performance",
                             "workforce_survey", "mixed") and org_risk:
            all_insights += generate_hr_insights(org_risk, model_auc, currency=_curr)
            action_plan   = generate_action_plan(org_risk)
        else:
            action_plan = {"30_day": [], "60_day": [], "90_day": []}

        if dataset_type == "biosignal_timeseries" and biosignal_context:
            all_insights += generate_biosignal_insights(
                signal_type   = biosignal_context.get("signal_type", "Signal"),
                global_stats  = biosignal_context.get("global_stats", {}),
                stress_score  = biosignal_context.get("stress_score", 0.0),
                quality_score = biosignal_context.get("quality_score", 0.0),
                anomaly_count = biosignal_context.get("anomaly_count", 0),
            )

        # Always add generic data intelligence insights
        all_insights += generate_generic_insights(
            quality_score, n_rows, n_cols, missing_pct,
            n_numeric, n_categorical, dataset_type,
        )

        # Sort by priority
        all_insights.sort(key=lambda i: i.priority)
        all_insights = all_insights[:MAX_INSIGHTS]

        # Executive summary
        if org_risk:
            rp  = org_risk.overall_attrition_risk
            ew  = org_risk.early_warning_level
            fin = org_risk.total_financial_exposure
            _c  = getattr(org_risk, "currency", "SAR")
            _cs = CURRENCY_SYMBOLS.get(_c, _c)
            exec_summary = (
                f"The workforce shows {rp:.0%} predicted attrition probability (Early Warning: {ew}). "
                f"Estimated financial exposure from projected departures: {_cs} {fin:,.0f}. "
                f"{org_risk.high_risk_employees} employees are in the priority review segment — "
                f"human validation required before any HR action."
            )
        else:
            exec_summary = (
                f"Dataset type: {dataset_type.replace('_', ' ').title()}. "
                f"Quality score: {quality_score:.0f}/100. "
                f"{n_rows:,} records analysed."
            )

        risk_headline = "Stable" if not org_risk else org_risk.early_warning_level

        return InsightReport(
            dataset_type              = dataset_type,
            insights                  = all_insights,
            executive_summary         = exec_summary,
            risk_headline             = risk_headline,
            recommended_actions_30d   = action_plan.get("30_day", []),
            recommended_actions_60d   = action_plan.get("60_day", []),
            recommended_actions_90d   = action_plan.get("90_day", []),
        )
