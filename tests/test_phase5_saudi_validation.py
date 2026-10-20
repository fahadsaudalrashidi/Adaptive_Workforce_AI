# -*- coding: utf-8 -*-
"""
test_phase5_saudi_validation.py
Phase 5 — Saudi Enterprise Validation Tests

Covers:
  1.  Saudi schema intelligence — ERP fingerprinting (IBM, SAP, Oracle, Mudad, Qiwa)
  2.  Arabic column detection and language profiling
  3.  Mixed Arabic-English bilingual schema handling
  4.  ERP-specific leakage column detection
  5.  PII column detection (Iqama, National ID, GOSI)
  6.  Saudi data governance — salary range validation (SAR)
  7.  Saudi data governance — age and tenure plausibility
  8.  Saudi data governance — attrition rate plausibility
  9.  Saudi data governance — duplicate record detection
  10. Unsupported construct mapping rejection
  11. Enterprise language guard — deterministic claim detection
  12. Enterprise language guard — legal-risk language detection
  13. Enterprise language guard — causal language detection
  14. Enterprise language guard — cultural sensitivity (nationality, gender)
  15. Enterprise language guard — PII exposure detection
  16. Enterprise language guard — compliant text passes
  17. Calibration reliability audit — high-risk concentration
  18. Calibration reliability audit — department instability
  19. Calibration reliability audit — fold instability
  20. Calibration reliability audit — false positive governance
  21. Cross-company schema adaptation (schema completeness scoring)
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def ibm_df():
    rng = np.random.default_rng(42)
    n = 60
    return pd.DataFrame({
        "Age":                       rng.integers(22, 58, n),
        "MonthlyIncome":             rng.integers(5000, 25000, n),
        "JobLevel":                  rng.integers(1, 5, n),
        "YearsAtCompany":            rng.integers(0, 20, n),
        "TotalWorkingYears":         rng.integers(1, 35, n),
        "JobSatisfaction":           rng.integers(1, 5, n),
        "EnvironmentSatisfaction":   rng.integers(1, 5, n),
        "RelationshipSatisfaction":  rng.integers(1, 5, n),
        "WorkLifeBalance":           rng.integers(1, 5, n),
        "JobInvolvement":            rng.integers(1, 5, n),
        "OverTime":                  rng.choice(["Yes", "No"], n),
        "PercentSalaryHike":         rng.integers(10, 25, n),
        "PerformanceRating":         rng.integers(1, 5, n),
        "Department":                rng.choice(["Sales", "R&D", "HR"], n),
        "Attrition":                 rng.choice(["Yes", "No"], n),
    })


@pytest.fixture
def arabic_df():
    """Dataset with Arabic column names (Mudad-style)."""
    rng = np.random.default_rng(1)
    n = 30
    return pd.DataFrame({
        "الراتب الأساسي":   rng.integers(5000, 20000, n),
        "العمر":            rng.integers(22, 55, n),
        "سنوات الخدمة":    rng.integers(0, 15, n),
        "الجنسية":          rng.choice(["سعودي", "غير سعودي"], n),
        "القسم":            rng.choice(["المبيعات", "الموارد البشرية"], n),
        "الرضا الوظيفي":   rng.integers(1, 5, n),
        "الاندماج الوظيفي": rng.integers(1, 5, n),
        "حالة الموظف":      rng.choice(["نشط", "منتهي"], n),
    })


@pytest.fixture
def oracle_df():
    """Dataset with Oracle HRMS-style columns."""
    rng = np.random.default_rng(2)
    n = 40
    return pd.DataFrame({
        "employee_number":        rng.integers(10000, 99999, n),
        "assignment_status_type": rng.choice(["ACTIVE_ASSIGN", "TERM_ASSIGN"], n),
        "grade_name":             rng.choice(["G1", "G2", "G3"], n),
        "organization_name":      rng.choice(["Sales", "HR"], n),
        "action_type":            rng.choice(["HIRE", "TERMINATION", "TRANSFER"], n),
        "action_reason":          rng.choice(["Resignation", "Retirement"], n),
        "effective_end_date":     rng.choice(["2024-12-31", None], n),
        "pay_annualized_salary":  rng.integers(60000, 240000, n),
    })


@pytest.fixture
def qiwa_df():
    """Dataset with Qiwa platform columns."""
    rng = np.random.default_rng(3)
    n = 25
    return pd.DataFrame({
        "nitaqat_band":        rng.choice(["Platinum", "High Green"], n),
        "saudization_pct":     rng.uniform(20, 80, n),
        "contract_type":       rng.choice(["Fixed", "Open-Ended"], n),
        "contract_end_date":   rng.choice(["2025-06-30", None], n),
        "work_permit_expiry":  ["2026-01-01"] * n,
        "mol_number":          rng.integers(1000000, 9999999, n),
    })


@pytest.fixture
def governance_violation_df():
    """DataFrame with salary and age governance violations."""
    return pd.DataFrame({
        "MonthlyIncome": [0, 500, 120000, 200000, 10000, 8000, 9000],
        "Age":           [10, 22, 30, 35, 200, 45, 50],
        "YearsAtCompany":[0, 2, 5, 50, 3, 4, 6],
        "Attrition":     ["No", "Yes", "No", "No", "Yes", "No", "Yes"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 1: Saudi Schema Intelligence — ERP Fingerprinting
# ─────────────────────────────────────────────────────────────────────────────

class TestSaudiSchemaIntelligence:

    def test_ibm_dataset_fingerprinted_as_ibm(self, ibm_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(ibm_df)
        assert report.erp_system_detected == "IBM_HR_BENCHMARK", (
            f"IBM dataset must be fingerprinted as IBM_HR_BENCHMARK. Got: {report.erp_system_detected}"
        )
        assert report.erp_confidence in ("HIGH", "MEDIUM")

    def test_oracle_dataset_fingerprinted_as_oracle(self, oracle_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(oracle_df)
        assert report.erp_system_detected == "ORACLE_HRMS", (
            f"Oracle dataset must be fingerprinted. Got: {report.erp_system_detected}"
        )

    def test_qiwa_dataset_fingerprinted(self, qiwa_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(qiwa_df)
        assert report.erp_system_detected == "QIWA_PLATFORM", (
            f"Qiwa dataset must be fingerprinted. Got: {report.erp_system_detected}"
        )

    def test_arabic_df_detected_as_arabic_dominant(self, arabic_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(arabic_df)
        assert report.language_profile == "arabic_dominant", (
            f"Arabic columns must produce arabic_dominant profile. Got: {report.language_profile}"
        )
        assert report.n_arabic > 0

    def test_ibm_df_is_english_dominant(self, ibm_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(ibm_df)
        assert report.language_profile == "english_dominant"

    def test_oracle_action_reason_flagged_as_leakage(self, oracle_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(oracle_df)
        assert report.n_leakage_risk >= 1, (
            "Oracle action_reason must be flagged as leakage"
        )

    def test_oracle_effective_end_date_flagged_as_leakage(self, oracle_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(oracle_df)
        leakage_lower = [c.lower() for c in report.leakage_columns]
        assert any("end_date" in c or "end" in c for c in leakage_lower), (
            "effective_end_date must be in leakage_columns"
        )

    def test_ibm_schema_completeness_high(self, ibm_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(ibm_df)
        assert report.schema_completeness_score >= 0.70, (
            f"IBM dataset should have high schema completeness. Got: {report.schema_completeness_score}"
        )

    def test_arabic_df_schema_completeness_low(self, arabic_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(arabic_df)
        assert report.schema_completeness_score < 0.70, (
            "Arabic-only dataset without IBM columns should have low completeness score"
        )

    def test_iqama_column_flagged_as_pii(self):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        df = pd.DataFrame({"iqama_number": ["1234567890"] * 5, "Age": [30] * 5})
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(df)
        assert report.n_pii >= 1, "Iqama number must be flagged as PII"

    def test_national_id_flagged_as_pii(self):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        df = pd.DataFrame({"national_id": ["1234567890"] * 5, "Age": [30] * 5})
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(df)
        assert report.n_pii >= 1, "National ID must be flagged as PII"

    def test_report_has_summary_string(self, ibm_df):
        from backend.core.saudi_schema_intelligence import analyse_schema
        report = analyse_schema(ibm_df)
        assert isinstance(report.summary, str) and len(report.summary) > 10

    def test_convenience_function(self, ibm_df):
        from backend.core.saudi_schema_intelligence import analyse_schema
        report = analyse_schema(ibm_df)
        assert report.n_columns == len(ibm_df.columns)

    def test_qiwa_contract_end_date_flagged_as_leakage(self, qiwa_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(qiwa_df)
        assert report.n_leakage_risk >= 1, (
            "contract_end_date in Qiwa export must be flagged as potential leakage"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 2: Saudi Data Governance
# ─────────────────────────────────────────────────────────────────────────────

class TestSaudiDataGovernance:

    def test_annual_salary_flagged_as_suspicious(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"MonthlyIncome": [120000, 150000, 130000, 140000, 160000]})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, salary_col="MonthlyIncome")
        assert report.salary_currency_suspected == "SAR_annual", (
            "High salary values should be detected as likely annual SAR"
        )
        assert report.n_high >= 1

    def test_zero_salary_flagged_as_high(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"MonthlyIncome": [0, 0, 8000, 10000, 12000]})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, salary_col="MonthlyIncome")
        assert any(f.finding_type == "SALARY_ZERO_VALUES" for f in report.findings)

    def test_age_below_minimum_is_critical(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"Age": [10, 12, 30, 35, 40]})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, age_col="Age")
        assert report.n_critical >= 1
        assert any(f.finding_type == "AGE_BELOW_MINIMUM" for f in report.findings)

    def test_impossible_age_is_high(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"Age": [90, 100, 200, 30, 35]})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, age_col="Age")
        assert any(f.finding_type == "AGE_IMPOSSIBLE" for f in report.findings)

    def test_negative_tenure_is_critical(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"YearsAtCompany": [-5, -1, 2, 5, 10]})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, tenure_col="YearsAtCompany")
        assert any(f.finding_type == "TENURE_NEGATIVE" for f in report.findings)
        assert report.n_critical >= 1

    def test_impossible_tenure_is_high(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"YearsAtCompany": [50, 60, 2, 5, 8]})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, tenure_col="YearsAtCompany")
        assert any(f.finding_type == "TENURE_IMPOSSIBLE" for f in report.findings)

    def test_high_attrition_rate_flagged(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"Attrition": ["Yes"] * 70 + ["No"] * 30})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, target_col="Attrition")
        assert any(f.finding_type == "ATTRITION_RATE_SUSPICIOUS" for f in report.findings)
        assert report.attrition_rate_observed is not None
        assert report.attrition_rate_observed > 0.5

    def test_normal_attrition_rate_not_flagged(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({"Attrition": ["Yes"] * 15 + ["No"] * 85})
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df, target_col="Attrition")
        att_flags = [f for f in report.findings if "ATTRITION_RATE" in f.finding_type]
        assert len(att_flags) == 0, "Normal attrition rate should not be flagged"

    def test_duplicate_records_flagged(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        row = {"Age": 30, "MonthlyIncome": 10000}
        df = pd.DataFrame([row] * 10 + [{"Age": 25, "MonthlyIncome": 8000}] * 5)
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df)
        assert any(f.finding_type == "DUPLICATE_RECORDS" for f in report.findings)

    def test_exit_reason_leakage_detected(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({
            "exit_reason": ["Resignation", "Retirement", None] * 5,
            "Age": [30, 60, 35] * 5,
        })
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df)
        assert "exit_reason" in report.leakage_columns_detected

    def test_arabic_exit_reason_leakage_detected(self):
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        df = pd.DataFrame({
            "سبب الخروج": ["استقالة", "تقاعد", None] * 4,
            "العمر": [30, 60, 35, 28] * 3,
        })
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(df)
        assert len(report.leakage_columns_detected) >= 1

    def test_clean_ibm_df_is_clean(self, ibm_df):
        """Standard IBM HR dataset should pass Saudi governance checks."""
        from backend.core.saudi_data_governance import SaudiDataGovernanceEngine
        engine = SaudiDataGovernanceEngine()
        report = engine.validate(ibm_df, target_col="Attrition",
                                 salary_col="MonthlyIncome",
                                 age_col="Age", tenure_col="YearsAtCompany")
        # IBM data has SAR-range salaries after our fixture setup
        # No critical leakage or PII columns
        assert report.n_critical == 0 or all(
            f.finding_type in ("SALARY_SCALE_SUSPICIOUS",)
            for f in report.findings if f.severity == "CRITICAL"
        ), f"IBM df should be clean. Critical findings: {[f.finding_type for f in report.findings if f.severity == 'CRITICAL']}"

    def test_convenience_function(self):
        from backend.core.saudi_data_governance import validate_saudi_data
        df = pd.DataFrame({"Age": [30, 35, 40], "MonthlyIncome": [8000, 12000, 15000]})
        report = validate_saudi_data(df)
        assert isinstance(report.summary, str)


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 3: Enterprise Language Guard
# ─────────────────────────────────────────────────────────────────────────────

class TestEnterpriseLanguageGuard:

    def test_will_resign_is_critical(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("This employee will resign next month.")
        assert report.n_critical >= 1
        assert not report.is_compliant

    def test_will_leave_is_critical(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("Based on the analysis, the employee will leave.")
        assert report.n_critical >= 1

    def test_termination_language_is_critical(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("We recommend termination of this employee.")
        assert report.n_critical >= 1
        legal_violations = [v for v in report.violations if v.category == "LEGAL_RISK"]
        assert len(legal_violations) >= 1

    def test_fire_language_is_critical(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("The manager should fire this employee immediately.")
        crit = [v for v in report.violations if v.severity == "CRITICAL"]
        assert len(crit) >= 1

    def test_causal_language_flagged(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("Low satisfaction causes attrition in this department.")
        causal = [v for v in report.violations if v.category == "CAUSAL_LANGUAGE"]
        assert len(causal) >= 1

    def test_certain_to_leave_is_critical(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("Employee #42 is certain to leave.")
        assert report.n_critical >= 1

    def test_medical_language_flagged(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("This employee shows clinical burnout diagnosis symptoms.")
        medical = [v for v in report.violations if v.category == "MEDICAL_LANGUAGE"]
        assert len(medical) >= 1

    def test_nationality_attrition_link_flagged(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("Saudi employees show lower attrition risk than non-Saudi employees.")
        cultural = [v for v in report.violations if v.category == "CULTURAL_SENSITIVITY"]
        assert len(cultural) >= 1

    def test_gender_attrition_link_flagged(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("Female employees have higher attrition risk than male employees.")
        cultural = [v for v in report.violations if v.category == "CULTURAL_SENSITIVITY"]
        assert len(cultural) >= 1

    def test_probabilistic_language_is_compliant(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        safe_text = (
            "Employees in the priority review segment show elevated predicted "
            "probability of voluntary separation. Human validation is required "
            "before any personnel action."
        )
        report = guard.audit(safe_text)
        assert report.is_compliant, (
            f"Probabilistic, governance-safe language must pass audit. "
            f"Violations: {[(v.matched_text, v.category) for v in report.violations]}"
        )

    def test_empty_text_is_compliant(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("")
        assert report.is_compliant

    def test_safe_text_generated(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("This employee will resign within 6 months.")
        assert report.safe_text is not None
        assert report.safe_text != "This employee will resign within 6 months."

    def test_batch_audit(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        texts = ["Safe language here.", "This employee will resign.", ""]
        reports = guard.audit_batch(texts)
        assert len(reports) == 3
        assert reports[0].is_compliant
        assert not reports[1].is_compliant
        assert reports[2].is_compliant

    def test_convenience_functions(self):
        from backend.core.enterprise_language_guard import audit_language, is_language_compliant
        assert is_language_compliant("Elevated predicted risk detected.")
        assert not is_language_compliant("Employee will resign next week.")
        report = audit_language("Employee shows elevated risk.")
        assert isinstance(report.summary, str)

    def test_100_percent_claim_is_critical(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("There is a 100% chance this employee will leave.")
        assert report.n_critical >= 1

    def test_must_be_removed_is_critical(self):
        from backend.core.enterprise_language_guard import EnterpriseLanguageGuard
        guard = EnterpriseLanguageGuard()
        report = guard.audit("This employee must be removed from the team.")
        assert report.n_critical >= 1


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 4: Calibration Reliability Audit
# ─────────────────────────────────────────────────────────────────────────────

class TestCalibrationReliabilityAudit:

    def _make_probs(self, rng, n=200, attrition_rate=0.16):
        y_true = rng.choice([0, 1], n, p=[1 - attrition_rate, attrition_rate])
        y_prob = np.clip(y_true * 0.4 + rng.uniform(0, 0.5, n), 0.0, 1.0)
        return y_true.astype(float), y_prob

    def test_high_risk_concentration_flagged(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(10)
        n = 100
        y_true = rng.choice([0, 1], n)
        y_prob = np.full(n, 0.80)   # everyone is "high risk"
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true.astype(float), y_prob=y_prob)
        assert report.high_risk_concentration_flag
        assert report.pct_high_risk > 0.40

    def test_normal_concentration_not_flagged(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(11)
        y_true, y_prob = self._make_probs(rng)
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob)
        assert not report.high_risk_concentration_flag

    def test_small_department_flagged_as_unreliable(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(12)
        y_true, y_prob = self._make_probs(rng, n=30)
        depts = pd.Series(["Big Dept"] * 27 + ["Tiny"] * 3)
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob, department_series=depts)
        assert report.n_critical_small_depts >= 1

    def test_reliable_departments_not_flagged(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(13)
        y_true, y_prob = self._make_probs(rng, n=100)
        depts = pd.Series(["Sales"] * 50 + ["HR"] * 50)
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob, department_series=depts)
        assert report.n_critical_small_depts == 0
        assert report.n_unreliable_depts == 0

    def test_fold_instability_flagged(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(14)
        y_true, y_prob = self._make_probs(rng)
        unstable_folds = [0.60, 0.92, 0.55, 0.88, 0.61]
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob, fold_aucs=unstable_folds)
        assert report.fold_instability_flag
        assert report.fold_auc_std > 0.08

    def test_stable_folds_not_flagged(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(15)
        y_true, y_prob = self._make_probs(rng)
        stable_folds = [0.82, 0.83, 0.81, 0.84, 0.82]
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob, fold_aucs=stable_folds)
        assert not report.fold_instability_flag

    def test_none_inputs_return_not_evaluated(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=None, y_prob=None)
        assert report.overall_reliability == "NOT_EVALUATED"

    def test_risk_band_reliability_computed(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(16)
        y_true, y_prob = self._make_probs(rng, n=300)
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob)
        assert len(report.risk_band_reliability) >= 1, (
            "At least one risk band should have employees"
        )

    def test_false_positive_rate_computed(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(17)
        y_true, y_prob = self._make_probs(rng, n=200)
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob, decision_threshold=0.55)
        # With a random-ish model, FP rate should be computable
        # (if any employees are above threshold)
        assert report.fp_rate_high_risk_tier is not None or report.pct_high_risk < 0.01

    def test_convenience_function(self):
        from backend.core.calibration_reliability_audit import audit_calibration_reliability
        rng = np.random.default_rng(18)
        y_true, y_prob = self._make_probs(rng)
        report = audit_calibration_reliability(y_true=y_true, y_prob=y_prob)
        assert isinstance(report.summary, str)
        assert hasattr(report, "base_calibration")

    def test_overall_reliability_is_string(self):
        from backend.core.calibration_reliability_audit import CalibrationReliabilityAuditor
        rng = np.random.default_rng(19)
        y_true, y_prob = self._make_probs(rng)
        auditor = CalibrationReliabilityAuditor()
        report = auditor.audit(y_true=y_true, y_prob=y_prob)
        assert report.overall_reliability in ("RELIABLE", "UNRELIABLE", "CRITICAL", "NOT_EVALUATED")


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 5: Cross-Company Schema Adaptation
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossCompanySchemaAdaptation:

    def test_different_erps_produce_different_fingerprints(self, ibm_df, oracle_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        ibm_report = engine.analyse(ibm_df)
        oracle_report = engine.analyse(oracle_df)
        assert ibm_report.erp_system_detected != oracle_report.erp_system_detected

    def test_missing_constructs_reported(self):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        df = pd.DataFrame({
            "Age": [30, 35],
            "Department": ["Sales", "HR"],
        })
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(df)
        assert len(report.missing_required_constructs) >= 5, (
            "A dataset with only Age and Department should have many missing IBM constructs"
        )

    def test_governance_notes_populated_for_oracle(self, oracle_df):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(oracle_df)
        oracle_notes = [n for n in report.governance_notes if "ORACLE" in n.upper()]
        assert len(oracle_notes) >= 1

    def test_governance_notes_populated_for_mudad(self):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        df = pd.DataFrame({
            "الراتب الأساسي": [8000, 10000, 12000],
            "بدل سكن": [2000, 2000, 2000],
            "رقم الإقامة": ["1234567890"] * 3,
        })
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(df)
        # Should detect Arabic columns and PII
        assert report.n_pii >= 1
        assert report.n_arabic >= 1

    def test_bilingual_df_has_bilingual_profile(self):
        from backend.core.saudi_schema_intelligence import SaudiSchemaIntelligenceEngine
        df = pd.DataFrame({
            "Age": [30, 35],
            "الراتب الأساسي": [8000, 10000],
            "Department": ["Sales", "HR"],
            "الرضا الوظيفي": [3, 4],
        })
        engine = SaudiSchemaIntelligenceEngine()
        report = engine.analyse(df)
        assert report.language_profile == "bilingual", (
            f"Mix of Arabic and English columns must produce bilingual profile. "
            f"Got: {report.language_profile}"
        )
        assert report.n_arabic >= 2
        assert report.n_english >= 2
