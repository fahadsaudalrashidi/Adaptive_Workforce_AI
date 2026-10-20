"""
Phase 6 — Enterprise Commercialization & Deployment Architecture Tests.

Covers:
  - ROIEstimationEngine: estimates, ranges, assumptions
  - ExecutiveReportingLayer: language compliance, department summaries
  - Export safety (PII exclusion)
  - Executive reporting safety

Phase 39: EnterpriseOnboardingPipeline (backend/core/enterprise_onboarding_pipeline.py)
was removed — it had zero live route/consumer wiring (confirmed dead code)
and existed solely to onboard data into the deleted theory-construct system
("Theory Compatibility Scan" was one of its 7 stages). The
TestEnterpriseOnboardingPipeline class (18 tests) and its exclusive fixtures
(small_df, empty_df, leakage_df, pii_df, arabic_df) were removed with it, and
the 2 onboarding-based tests inside TestEnterpriseExportSafety were removed
too — see PHASE_39_PREDICTION_REMOVAL_AND_ENTERPRISE_REBRAND_REPORT.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.core.roi_estimation_engine import (
    ROIEstimationEngine,
    BusinessValueReport,
    estimate_business_value,
)
from backend.core.executive_reporting_layer import (
    ExecutiveReportingLayer,
    ExecutiveReport,
    RELIABILITY_RELIABLE,
    RELIABILITY_CRITICAL,
    RELIABILITY_NOT_EVALUATED,
    generate_executive_report,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def ibm_df():
    """Minimal IBM-like dataset sufficient to pass all onboarding stages."""
    np.random.seed(42)
    n = 200
    return pd.DataFrame({
        "EmployeeNumber": range(1, n + 1),
        "Age": np.random.randint(25, 55, n),
        "MonthlyIncome": np.random.randint(5000, 25000, n),
        "JobSatisfaction": np.random.randint(1, 5, n),
        "EnvironmentSatisfaction": np.random.randint(1, 5, n),
        "RelationshipSatisfaction": np.random.randint(1, 5, n),
        "WorkLifeBalance": np.random.randint(1, 5, n),
        "JobInvolvement": np.random.randint(1, 5, n),
        "JobLevel": np.random.randint(1, 6, n),
        "YearsAtCompany": np.random.randint(0, 20, n),
        "TotalWorkingYears": np.random.randint(1, 30, n),
        "YearsInCurrentRole": np.random.randint(0, 10, n),
        "PercentSalaryHike": np.random.randint(10, 25, n),
        "OverTime": np.random.choice(["Yes", "No"], n),
        "Department": np.random.choice(["Sales", "R&D", "HR", "Finance"], n),
        "Attrition": np.random.choice([0, 1], n, p=[0.84, 0.16]),
    })


@pytest.fixture
def y_prob_ibm(ibm_df):
    """Synthetic probability scores for IBM fixture."""
    np.random.seed(99)
    return pd.Series(np.random.beta(2, 5, len(ibm_df)))


@pytest.fixture
def high_concentration_prob(ibm_df):
    """Probabilities where >60% are high-risk — concentration flag scenario."""
    return pd.Series(np.full(len(ibm_df), 0.75))


# ═══════════════════════════════════════════════════════════════════════════════
# TestROIEstimationEngine
# ═══════════════════════════════════════════════════════════════════════════════

class TestROIEstimationEngine:

    def test_returns_business_value_report(self, ibm_df, y_prob_ibm):
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        assert isinstance(report, BusinessValueReport)

    def test_estimates_present_when_high_risk_exists(self, ibm_df, y_prob_ibm):
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        assert len(report.estimates) > 0

    def test_cost_range_is_valid(self, ibm_df, y_prob_ibm):
        """Low estimate must be ≤ high estimate for all scenarios."""
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        for est in report.estimates:
            assert est.estimated_cost_low_sar <= est.estimated_cost_high_sar, (
                f"{est.scenario_name}: low ({est.estimated_cost_low_sar}) > high ({est.estimated_cost_high_sar})"
            )

    def test_assumptions_always_populated(self, ibm_df, y_prob_ibm):
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        for est in report.estimates:
            assert len(est.assumptions) > 0, f"{est.scenario_name} has no assumptions"

    def test_uncertainty_note_always_present(self, ibm_df, y_prob_ibm):
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        for est in report.estimates:
            assert est.uncertainty_notes, f"{est.scenario_name} has no uncertainty note"

    def test_governance_notes_populated(self, ibm_df, y_prob_ibm):
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        assert len(report.governance_notes) > 0

    def test_no_predictions_produces_warning(self, ibm_df):
        report = estimate_business_value(ibm_df, y_prob=None)
        assert len(report.governance_warnings) > 0

    def test_n_high_risk_count_correct(self, ibm_df):
        y_prob = pd.Series([0.8] * 50 + [0.2] * 150)
        report = estimate_business_value(ibm_df, y_prob=y_prob, high_risk_threshold=0.6)
        assert report.n_high_risk == 50

    def test_salary_col_used_when_provided(self, ibm_df, y_prob_ibm):
        report_with = estimate_business_value(ibm_df, y_prob=y_prob_ibm, salary_col="MonthlyIncome")
        report_without = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        # With salary column, estimates should use real median vs default — just check no crash
        assert isinstance(report_with, BusinessValueReport)
        assert isinstance(report_without, BusinessValueReport)

    def test_department_estimates_generated(self, ibm_df, y_prob_ibm):
        report = estimate_business_value(
            ibm_df, y_prob=y_prob_ibm,
            salary_col="MonthlyIncome",
            department_col="Department",
            high_risk_threshold=0.3,
        )
        dept_estimates = [e for e in report.estimates if "Department" in e.scenario_name]
        assert len(dept_estimates) > 0

    def test_retention_opportunity_is_subset_of_exposure(self, ibm_df, y_prob_ibm):
        """Retention opportunity (partial prevention) must be ≤ full exposure."""
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm, high_risk_threshold=0.3)
        if report.retention_opportunity_high_sar > 0 and report.annual_exposure_high_sar > 0:
            assert report.retention_opportunity_high_sar <= report.annual_exposure_high_sar

    def test_zero_high_risk_produces_no_cost_estimate(self, ibm_df):
        y_all_low = pd.Series(np.full(len(ibm_df), 0.1))
        report = estimate_business_value(ibm_df, y_prob=y_all_low, high_risk_threshold=0.6)
        assert report.n_high_risk == 0
        exposure_ests = [e for e in report.estimates if e.scenario_name == "Annual Turnover Cost Exposure"]
        assert len(exposure_ests) == 0

    def test_assumptions_cite_sources(self, ibm_df, y_prob_ibm):
        """Assumption text must include a source reference."""
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm)
        assert report.assumptions is not None
        assert report.assumptions.multiplier_source
        assert "SHRM" in report.assumptions.multiplier_source or "CIPD" in report.assumptions.multiplier_source


# ═══════════════════════════════════════════════════════════════════════════════
# TestExecutiveReportingLayer
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutiveReportingLayer:

    def test_returns_executive_report(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        assert isinstance(report, ExecutiveReport)

    def test_narrative_is_language_compliant(self, ibm_df, y_prob_ibm):
        """Executive narrative must pass the enterprise language guard."""
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        assert report.language_compliant, (
            f"Language violations detected in executive report: "
            f"{report.language_violations_detected} violation(s)"
        )

    def test_no_deterministic_claims_in_narrative(self, ibm_df, y_prob_ibm):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard, CAT_DETERMINISTIC_CLAIM
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        guard = EnterpriseLanguageGuard()
        audit = guard.audit(report.executive_narrative)
        det_violations = [v for v in audit.violations if v.category == CAT_DETERMINISTIC_CLAIM]
        assert len(det_violations) == 0

    def test_department_summaries_generated(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(
            ibm_df, y_prob=y_prob_ibm, department_col="Department"
        )
        assert len(report.department_summaries) > 0

    def test_department_summaries_sorted_by_risk(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(
            ibm_df, y_prob=y_prob_ibm, department_col="Department"
        )
        if len(report.department_summaries) >= 2:
            scores = [s.mean_risk_score for s in report.department_summaries]
            assert scores == sorted(scores, reverse=True)

    def test_high_concentration_flag_set(self, ibm_df, high_concentration_prob):
        report = generate_executive_report(ibm_df, y_prob=high_concentration_prob)
        assert report.organization_summary.high_risk_concentration_flag
        assert report.high_risk_concentration_alert is not None

    def test_concentration_alert_is_language_compliant(self, ibm_df, high_concentration_prob):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        report = generate_executive_report(ibm_df, y_prob=high_concentration_prob)
        if report.high_risk_concentration_alert:
            guard = EnterpriseLanguageGuard()
            audit = guard.audit(report.high_risk_concentration_alert)
            assert audit.is_compliant

    def test_critical_reliability_adds_governance_note(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(
            ibm_df, y_prob=y_prob_ibm,
            calibration_reliability=RELIABILITY_CRITICAL
        )
        critical_notes = [n for n in report.governance_notes if "CRITICAL" in n]
        assert len(critical_notes) > 0

    def test_org_summary_fractions_sum_to_one(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        total = (
            report.organization_summary.fraction_low_risk
            + report.organization_summary.fraction_medium_risk
            + report.organization_summary.fraction_high_risk
        )
        assert abs(total - 1.0) < 0.01, f"Fractions sum to {total}, expected 1.0"

    def test_intervention_recommendations_not_empty(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        assert len(report.intervention_recommendation_categories) > 0

    def test_recommendations_language_compliant(self, ibm_df, y_prob_ibm):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        guard = EnterpriseLanguageGuard()
        for rec in report.intervention_recommendation_categories:
            audit = guard.audit(rec)
            assert audit.is_compliant, f"Non-compliant recommendation: {rec}"

    def test_no_individual_employee_data_in_report(self, ibm_df, y_prob_ibm):
        """Verify EmployeeNumber column name and employee ID patterns are absent from narrative."""
        report = generate_executive_report(
            ibm_df, y_prob=y_prob_ibm, department_col="Department"
        )
        # Column name must not appear in narrative
        assert "EmployeeNumber" not in report.executive_narrative
        # Pattern "Employee 1" (ID-style reference) must not appear
        import re
        assert not re.search(r"Employee\s+\d+", report.executive_narrative)

    def test_volatility_indicator_valid_value(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        assert report.organization_summary.workforce_volatility_indicator in (
            "LOW", "ELEVATED", "HIGH", "CRITICAL"
        )

    def test_governance_notes_populated(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        assert len(report.governance_notes) > 0

    def test_unreliable_small_dept_flagged(self, ibm_df, y_prob_ibm):
        """A department with <10 employees should be flagged as unreliable."""
        df_mod = ibm_df.copy()
        # Add a tiny department
        tiny_dept = pd.DataFrame({col: [ibm_df[col].iloc[0]] * 3 for col in ibm_df.columns})
        tiny_dept["Department"] = "TinyTeam"
        df_all = pd.concat([ibm_df, tiny_dept], ignore_index=True)
        prob_all = pd.concat([y_prob_ibm, pd.Series([0.5, 0.5, 0.5])], ignore_index=True)
        report = generate_executive_report(df_all, y_prob=prob_all, department_col="Department")
        tiny_summary = next((s for s in report.department_summaries if s.department == "TinyTeam"), None)
        assert tiny_summary is not None
        assert not tiny_summary.is_reliable

    def test_fold_auc_std_instability_noted(self, ibm_df, y_prob_ibm):
        report = generate_executive_report(
            ibm_df, y_prob=y_prob_ibm, fold_auc_std=0.15
        )
        stability_notes = [n for n in report.governance_notes if "Cross-fold" in n or "stability" in n.lower()]
        assert len(stability_notes) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestEnterpriseExportSafety
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseExportSafety:

    def test_executive_report_no_employee_ids(self, ibm_df, y_prob_ibm):
        """Executive report must not expose EmployeeNumber column name or ID-style patterns."""
        import re
        report = generate_executive_report(ibm_df, y_prob=y_prob_ibm)
        full_text = report.executive_narrative + report.summary
        assert "EmployeeNumber" not in full_text
        assert not re.search(r"Employee\s+\d+", full_text)

    def test_roi_estimates_include_uncertainty(self, ibm_df, y_prob_ibm):
        """Every estimate must have uncertainty_notes — prevents presenting as guarantees."""
        report = estimate_business_value(ibm_df, y_prob=y_prob_ibm, high_risk_threshold=0.3)
        for est in report.estimates:
            assert len(est.uncertainty_notes) > 10, (
                f"Estimate '{est.scenario_name}' has insufficient uncertainty notes"
            )
