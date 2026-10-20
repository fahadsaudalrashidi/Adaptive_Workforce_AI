"""
ROI Estimation Engine — Phase 6.

Produces defensible, assumption-cited business value estimates for attrition
risk intelligence. All estimates are presented as ranges with explicit
uncertainty notes. No specific savings percentages are guaranteed.

Assumption sources:
  - SHRM (2022): "The True Cost of Turnover" — replacement cost 50–200% annual salary
  - Gulf HR Benchmark (CIPD Middle East, 2023): adjusted multipliers for Saudi market
  - Intervention effectiveness: conservative literature range 25–50% retention improvement
    (Hom et al., 2017, Journal of Management review)

NEVER:
  - Claim guaranteed savings
  - Present point estimates without ranges
  - Use fabricated market benchmarks
  - Apply non-Saudi cost structures to Saudi deployments
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# Phase 34 consolidation note: this module (roi_estimation_engine.py) is not
# reachable from any live entry point — its only reference anywhere in the
# codebase is tests/test_phase6_enterprise_deployment.py, superseded in
# production by executive_roi_engine.py. It is kept, and its default salary
# constant is now sourced from the single canonical financial module instead
# of a locally-hardcoded flat figure, per the Phase 0 consolidation mandate.
# Its own replacement-multiplier methodology (below) is a distinct, already
# range-based/cited model and is left as-is rather than being force-merged
# into the 9-component Cascio-Boudreau model used elsewhere — the two are
# compatible alternative estimates, not literal duplicates of one formula.
from backend.core.financial_intelligence_engine import (
    estimate_monthly_salary as _canonical_estimate_monthly_salary,
)

# ── Saudi market replacement cost assumptions ──────────────────────────────
# Source: CIPD Middle East HR Benchmark 2023, adjusted for Saudi labour market.
# Conservative range used to avoid overstating potential savings.
_REPLACEMENT_MULTIPLIER_LOW = 1.5   # × monthly salary
_REPLACEMENT_MULTIPLIER_HIGH = 2.5  # × monthly salary

# Senior/specialist role premium (roles with JobLevel ≥ 4)
_SENIOR_REPLACEMENT_MULTIPLIER_LOW = 2.5
_SENIOR_REPLACEMENT_MULTIPLIER_HIGH = 4.0

# Default monthly salary if no salary data available — now the single
# canonical default (SECTOR_SALARY_SAR["diversified"] x SENIORITY_SALARY_MULT["mid"]
# in financial_intelligence_engine.py) instead of a separately-hardcoded SAR 8,000.
_DEFAULT_MONTHLY_SALARY_SAR = _canonical_estimate_monthly_salary("diversified", "mid")

# Intervention effectiveness range (fraction of high-risk employees retained
# through targeted HR intervention — conservative literature range)
_INTERVENTION_EFFECTIVENESS_LOW = 0.25
_INTERVENTION_EFFECTIVENESS_HIGH = 0.50

# High-risk probability threshold for counting "at-risk" employees
_HIGH_RISK_THRESHOLD = 0.60

# Senior role threshold (if JobLevel column available)
_SENIOR_JOB_LEVEL = 4

# Minimum sample size for reliable estimates
_MIN_RELIABLE_N = 50


@dataclass
class CostAssumptions:
    """Documents all assumptions used in a cost estimate."""
    replacement_multiplier_low: float
    replacement_multiplier_high: float
    monthly_salary_sar: float
    intervention_effectiveness_low: float
    intervention_effectiveness_high: float
    salary_source: str
    multiplier_source: str
    effectiveness_source: str


@dataclass
class ROIEstimate:
    """
    A single cost/value estimate with range and confidence qualifier.

    All financial figures are in SAR. Ranges reflect assumption uncertainty,
    not confidence intervals in the statistical sense.
    """
    scenario_name: str
    description: str
    estimated_cost_low_sar: float
    estimated_cost_high_sar: float
    confidence: str  # LOW / MEDIUM / HIGH — reflects data quality, not statistical CI
    n_employees_in_scope: int
    assumptions: list[str] = field(default_factory=list)
    uncertainty_notes: str = ""


@dataclass
class BusinessValueReport:
    """
    Complete business value assessment for one organization.

    All figures are indicative estimates based on cited assumptions.
    They are not financial projections and must not be presented as guarantees.
    """
    n_employees_total: int
    n_high_risk: int
    high_risk_fraction: float
    estimates: list[ROIEstimate] = field(default_factory=list)
    assumptions: CostAssumptions = None
    governance_warnings: list[str] = field(default_factory=list)
    governance_notes: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def annual_exposure_low_sar(self) -> float:
        for est in self.estimates:
            if est.scenario_name == "Annual Turnover Cost Exposure":
                return est.estimated_cost_low_sar
        return 0.0

    @property
    def annual_exposure_high_sar(self) -> float:
        for est in self.estimates:
            if est.scenario_name == "Annual Turnover Cost Exposure":
                return est.estimated_cost_high_sar
        return 0.0

    @property
    def retention_opportunity_low_sar(self) -> float:
        for est in self.estimates:
            if est.scenario_name == "Retention Opportunity Estimate":
                return est.estimated_cost_low_sar
        return 0.0

    @property
    def retention_opportunity_high_sar(self) -> float:
        for est in self.estimates:
            if est.scenario_name == "Retention Opportunity Estimate":
                return est.estimated_cost_high_sar
        return 0.0


class ROIEstimationEngine:
    """
    Produces governance-safe business value estimates.

    Stateless: each call to estimate() is independent.
    """

    def estimate(
        self,
        df: pd.DataFrame,
        y_prob: Optional[pd.Series] = None,
        salary_col: Optional[str] = None,
        job_level_col: Optional[str] = None,
        department_col: Optional[str] = None,
        high_risk_threshold: float = _HIGH_RISK_THRESHOLD,
    ) -> BusinessValueReport:
        """
        Compute business value estimates from risk scores and workforce data.

        Parameters
        ----------
        df : pd.DataFrame
            Workforce dataset (may include salary and job level columns).
        y_prob : pd.Series, optional
            Predicted attrition probabilities (0–1). If None, estimates are
            based on dataset characteristics only.
        salary_col : str, optional
            Column containing monthly salary (SAR). If None, default used.
        job_level_col : str, optional
            Column containing job level (1–5 scale). If None, senior premium skipped.
        department_col : str, optional
            Column containing department name. If None, dept-level estimates skipped.
        high_risk_threshold : float
            Probability threshold above which an employee is counted as high-risk.
        """
        warnings: list[str] = []
        notes: list[str] = []
        estimates: list[ROIEstimate] = []

        n_total = len(df)
        if n_total < _MIN_RELIABLE_N:
            warnings.append(
                f"Dataset has only {n_total} employees. Estimates at this scale have "
                "high uncertainty and should not be used for budget planning."
            )

        # ── Determine salary basis ──────────────────────────────────────────
        monthly_salary_sar, salary_source = self._determine_salary(df, salary_col, warnings)

        # ── Determine high-risk population ─────────────────────────────────
        if y_prob is not None:
            n_high_risk = int((y_prob >= high_risk_threshold).sum())
            high_risk_fraction = n_high_risk / n_total if n_total > 0 else 0.0
        else:
            # Without predictions, cannot estimate at-risk count
            n_high_risk = 0
            high_risk_fraction = 0.0
            warnings.append(
                "No predicted probabilities provided (y_prob=None). "
                "Turnover cost exposure estimates require model predictions."
            )

        # ── Build assumption record ─────────────────────────────────────────
        assumptions = CostAssumptions(
            replacement_multiplier_low=_REPLACEMENT_MULTIPLIER_LOW,
            replacement_multiplier_high=_REPLACEMENT_MULTIPLIER_HIGH,
            monthly_salary_sar=monthly_salary_sar,
            intervention_effectiveness_low=_INTERVENTION_EFFECTIVENESS_LOW,
            intervention_effectiveness_high=_INTERVENTION_EFFECTIVENESS_HIGH,
            salary_source=salary_source,
            multiplier_source="CIPD Middle East HR Benchmark 2023; SHRM 2022",
            effectiveness_source="Hom et al. (2017), Journal of Management — meta-analytic review",
        )

        # ── Estimate 1: Annual turnover cost exposure ──────────────────────
        if n_high_risk > 0:
            exposure_low = n_high_risk * monthly_salary_sar * _REPLACEMENT_MULTIPLIER_LOW
            exposure_high = n_high_risk * monthly_salary_sar * _REPLACEMENT_MULTIPLIER_HIGH
            confidence = "MEDIUM" if n_total >= _MIN_RELIABLE_N else "LOW"
            estimates.append(ROIEstimate(
                scenario_name="Annual Turnover Cost Exposure",
                description=(
                    f"Estimated replacement cost if all {n_high_risk} high-risk employees leave. "
                    "This is a worst-case exposure figure, not a prediction that all will leave."
                ),
                estimated_cost_low_sar=round(exposure_low, 0),
                estimated_cost_high_sar=round(exposure_high, 0),
                confidence=confidence,
                n_employees_in_scope=n_high_risk,
                assumptions=[
                    f"Replacement cost = {_REPLACEMENT_MULTIPLIER_LOW}–{_REPLACEMENT_MULTIPLIER_HIGH}× monthly salary",
                    f"Monthly salary basis: SAR {monthly_salary_sar:,.0f} ({salary_source})",
                    "All high-risk employees assumed to leave (conservative upper bound)",
                    f"High-risk defined as predicted probability ≥ {high_risk_threshold:.0%}",
                ],
                uncertainty_notes=(
                    "Actual replacement costs vary by role seniority, market conditions, "
                    "and recruitment channel. Saudi Nitaqat compliance costs are an "
                    "uncalibrated planning estimate only — no citable public source "
                    "quantifies a universal Saudization cost premium (see "
                    "financial_intelligence_engine.py's NITAQAT_PREMIUM_DISCLAIMER; this "
                    "module is confirmed dead relative to the live product — "
                    "PHASE_4_MODULES_REPORT.md — the figure here was previously a second, "
                    "different, uncited guess and has been corrected to match the single "
                    "canonical uncalibrated estimate rather than removed, in case this "
                    "module is ever revived). "
                    "This estimate does not account for productivity loss during transition."
                ),
            ))

        # ── Estimate 2: Senior role exposure premium ────────────────────────
        if job_level_col and job_level_col in df.columns and y_prob is not None:
            senior_mask = df[job_level_col] >= _SENIOR_JOB_LEVEL
            if senior_mask.any():
                n_senior_risk = int(((y_prob >= high_risk_threshold) & senior_mask).sum())
                if n_senior_risk > 0:
                    senior_salary = (
                        df.loc[senior_mask, salary_col].mean()
                        if salary_col and salary_col in df.columns
                        else monthly_salary_sar * 1.8
                    )
                    senior_exposure_low = n_senior_risk * senior_salary * _SENIOR_REPLACEMENT_MULTIPLIER_LOW
                    senior_exposure_high = n_senior_risk * senior_salary * _SENIOR_REPLACEMENT_MULTIPLIER_HIGH
                    estimates.append(ROIEstimate(
                        scenario_name="Senior Role Replacement Exposure",
                        description=(
                            f"Additional cost exposure for {n_senior_risk} high-risk senior employees "
                            f"(Job Level ≥ {_SENIOR_JOB_LEVEL}). Senior roles carry higher replacement costs."
                        ),
                        estimated_cost_low_sar=round(senior_exposure_low, 0),
                        estimated_cost_high_sar=round(senior_exposure_high, 0),
                        confidence="LOW" if n_senior_risk < 5 else "MEDIUM",
                        n_employees_in_scope=n_senior_risk,
                        assumptions=[
                            f"Senior replacement multiplier: {_SENIOR_REPLACEMENT_MULTIPLIER_LOW}–{_SENIOR_REPLACEMENT_MULTIPLIER_HIGH}× monthly salary",
                            f"Senior salary basis: SAR {senior_salary:,.0f}",
                            "Includes executive search, onboarding, and institutional knowledge costs",
                        ],
                        uncertainty_notes=(
                            f"Senior role estimates have LOW statistical reliability when n < 10. "
                            f"Current scope: {n_senior_risk} employees."
                        ),
                    ))

        # ── Estimate 3: Retention opportunity ──────────────────────────────
        if n_high_risk > 0:
            retained_low = n_high_risk * _INTERVENTION_EFFECTIVENESS_LOW
            retained_high = n_high_risk * _INTERVENTION_EFFECTIVENESS_HIGH
            opp_low = retained_low * monthly_salary_sar * _REPLACEMENT_MULTIPLIER_LOW
            opp_high = retained_high * monthly_salary_sar * _REPLACEMENT_MULTIPLIER_HIGH
            estimates.append(ROIEstimate(
                scenario_name="Retention Opportunity Estimate",
                description=(
                    f"Potential cost avoidance if targeted retention interventions retain "
                    f"{int(retained_low)}–{int(retained_high)} of the {n_high_risk} high-risk employees. "
                    "This is an estimate, not a guarantee. Intervention effectiveness depends on "
                    "organizational capacity, manager quality, and the specific drivers of each employee's risk."
                ),
                estimated_cost_low_sar=round(opp_low, 0),
                estimated_cost_high_sar=round(opp_high, 0),
                confidence="LOW",
                n_employees_in_scope=n_high_risk,
                assumptions=[
                    f"Intervention effectiveness: {int(_INTERVENTION_EFFECTIVENESS_LOW*100)}–{int(_INTERVENTION_EFFECTIVENESS_HIGH*100)}% of high-risk employees retained",
                    "Source: Hom et al. (2017) meta-analytic review of retention intervention studies",
                    "Assumes targeted, personalized interventions (not blanket retention bonuses)",
                    "Intervention cost not included — this is gross opportunity only",
                ],
                uncertainty_notes=(
                    "IMPORTANT: Intervention effectiveness varies substantially across organizations, "
                    "industries, and individual cases. The literature range of 25–50% is based on "
                    "studies with organizational interventions (manager coaching, workload adjustment, "
                    "career development). Blanket financial incentives typically achieve lower effectiveness. "
                    "This estimate must not be presented as a financial projection to stakeholders."
                ),
            ))

        # ── Estimate 4: Department instability cost (if dept available) ────
        if department_col and department_col in df.columns and y_prob is not None:
            dept_estimates = self._estimate_department_costs(
                df, y_prob, department_col, salary_col, monthly_salary_sar,
                high_risk_threshold, warnings
            )
            estimates.extend(dept_estimates)

        notes.append(
            "All estimates are indicative ranges based on published HR cost research. "
            "They are not financial projections and must not be used as guarantees in "
            "sales materials or investor communications."
        )
        notes.append(
            "Saudi-specific costs (Nitaqat compliance, HRDF contribution, end-of-service gratuity) "
            "are not included in these estimates. Actual replacement costs in the Saudi market "
            "may be 15–40% higher than the base multiplier range."
        )

        summary = (
            f"Business value assessment: {n_total} employees, "
            f"{n_high_risk} identified as high-risk "
            f"({high_risk_fraction:.1%} of workforce). "
            f"Turnover cost exposure: SAR {estimates[0].estimated_cost_low_sar:,.0f}–"
            f"{estimates[0].estimated_cost_high_sar:,.0f} (if all high-risk leave). "
            if estimates else
            f"Business value assessment: {n_total} employees. No predictions provided — cost exposure not estimated."
        )

        return BusinessValueReport(
            n_employees_total=n_total,
            n_high_risk=n_high_risk,
            high_risk_fraction=high_risk_fraction,
            estimates=estimates,
            assumptions=assumptions,
            governance_warnings=warnings,
            governance_notes=notes,
            summary=summary,
        )

    def _determine_salary(
        self, df: pd.DataFrame, salary_col: Optional[str], warnings: list[str]
    ) -> tuple[float, str]:
        if salary_col and salary_col in df.columns:
            try:
                median_salary = float(df[salary_col].median())
                if median_salary > 0:
                    return median_salary, f"median of '{salary_col}' column"
            except (TypeError, ValueError):
                pass
            warnings.append(
                f"Salary column '{salary_col}' could not be read as numeric. "
                f"Using default SAR {_DEFAULT_MONTHLY_SALARY_SAR:,.0f}."
            )

        # Try common salary column names
        for candidate in ["MonthlyIncome", "monthly_income", "Salary", "salary", "base_pay"]:
            if candidate in df.columns:
                try:
                    median_salary = float(df[candidate].median())
                    if median_salary > 0:
                        return median_salary, f"median of '{candidate}' column (auto-detected)"
                except (TypeError, ValueError):
                    pass

        warnings.append(
            f"No salary column found. Using Saudi median estimate of SAR {_DEFAULT_MONTHLY_SALARY_SAR:,.0f}/month. "
            "Provide salary_col for more accurate estimates."
        )
        return _DEFAULT_MONTHLY_SALARY_SAR, "Saudi median salary estimate (no salary column provided)"

    def _estimate_department_costs(
        self,
        df: pd.DataFrame,
        y_prob: pd.Series,
        department_col: str,
        salary_col: Optional[str],
        default_salary: float,
        threshold: float,
        warnings: list[str],
    ) -> list[ROIEstimate]:
        estimates = []
        depts = df[department_col].dropna().unique()

        dept_costs: list[dict] = []
        for dept in depts:
            mask = df[department_col] == dept
            dept_prob = y_prob[mask]
            n_dept = int(mask.sum())
            n_risk = int((dept_prob >= threshold).sum())

            if n_dept < 5:
                continue  # too small for reliable estimate

            if salary_col and salary_col in df.columns:
                try:
                    dept_salary = float(df.loc[mask, salary_col].median())
                except (TypeError, ValueError):
                    dept_salary = default_salary
            else:
                dept_salary = default_salary

            if n_risk > 0:
                cost_low = n_risk * dept_salary * _REPLACEMENT_MULTIPLIER_LOW
                cost_high = n_risk * dept_salary * _REPLACEMENT_MULTIPLIER_HIGH
                dept_costs.append({
                    "dept": dept,
                    "n_risk": n_risk,
                    "n_total": n_dept,
                    "cost_low": cost_low,
                    "cost_high": cost_high,
                })

        if dept_costs:
            dept_costs.sort(key=lambda x: x["cost_high"], reverse=True)
            top3 = dept_costs[:3]
            for dc in top3:
                confidence = "MEDIUM" if dc["n_risk"] >= 10 else "LOW"
                estimates.append(ROIEstimate(
                    scenario_name=f"Department Risk Exposure: {dc['dept']}",
                    description=(
                        f"{dc['dept']}: {dc['n_risk']} of {dc['n_total']} employees at high risk. "
                        "Estimated replacement cost if all high-risk employees in this department leave."
                    ),
                    estimated_cost_low_sar=round(dc["cost_low"], 0),
                    estimated_cost_high_sar=round(dc["cost_high"], 0),
                    confidence=confidence,
                    n_employees_in_scope=dc["n_risk"],
                    assumptions=[
                        f"Replacement multiplier: {_REPLACEMENT_MULTIPLIER_LOW}–{_REPLACEMENT_MULTIPLIER_HIGH}× monthly salary",
                        "Assumes all high-risk employees in this department leave (upper bound)",
                    ],
                    uncertainty_notes=(
                        "Department estimates with n < 10 have LOW confidence. "
                        "See CalibrationReliabilityAudit for department-level reliability assessment."
                    ),
                ))

        return estimates


def estimate_business_value(
    df: pd.DataFrame,
    y_prob: Optional[pd.Series] = None,
    salary_col: Optional[str] = None,
    job_level_col: Optional[str] = None,
    department_col: Optional[str] = None,
    high_risk_threshold: float = _HIGH_RISK_THRESHOLD,
) -> BusinessValueReport:
    """Convenience function wrapping ROIEstimationEngine.estimate()."""
    engine = ROIEstimationEngine()
    return engine.estimate(
        df=df,
        y_prob=y_prob,
        salary_col=salary_col,
        job_level_col=job_level_col,
        department_col=department_col,
        high_risk_threshold=high_risk_threshold,
    )
