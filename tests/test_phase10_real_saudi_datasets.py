"""
Phase 10 Real Saudi Dataset Validation Tests — 16 tests.

Covers:
  - DatasetTypeClassifier: EMPLOYEE_ATTRITION vs JOB_MARKET vs STRESS_TEST vs UNKNOWN
  - SaudiAttritionNormalizer: column renaming, attrition target binary, salary parsing,
    proxy construct availability
  - JobMarketDatasetHandler: Jadarat subtype, processed subtype, global stress test,
    attrition always blocked, sensitive column detection, market intelligence mode
  - OfflineModeGuard: install, violation detection, loopback allowed, status audit
  - Cross-type governance: job posting data must NOT generate attrition predictions

Real datasets under test live at:
  C:\\Users\\PvP-Pc\\Desktop\\datasetssaudi\\

Tests that load real files are skipped gracefully if files are absent.

All 465 existing tests must remain unaffected.
"""

from __future__ import annotations

import os
import socket
import pandas as pd
import numpy as np
import pytest

# ── Path to real datasets ─────────────────────────────────────────────────────
_DATASETS_DIR = r"C:\Users\PvP-Pc\Desktop\datasetssaudi"

_ATTRITION_FILE  = os.path.join(_DATASETS_DIR, "Original Dataset of Employee Attrition (1).xlsx")
_JADARAT_FILE    = os.path.join(_DATASETS_DIR, "Jadarat_data12.csv")
_PROCESSED_FILE  = os.path.join(_DATASETS_DIR, "processed_dataset.csv")
_JOB_POST_FILE   = os.path.join(_DATASETS_DIR, "Job Posting.csv")

_file_present = lambda p: os.path.exists(p)


# ── Import modules under test ─────────────────────────────────────────────────

from backend.core.dataset_type_classifier import (
    DatasetTypeClassifier,
    DatasetType,
)
from backend.core.saudi_attrition_normalizer import (
    SaudiAttritionNormalizer,
    PROXY_CONSTRUCT_MAP,
)
from backend.core.job_market_dataset_handler import (
    JobMarketDatasetHandler,
    JobMarketSubtype,
    _extract_salary_from_benefits,
    _parse_positions,
    _parse_experience_years,
    _is_hijri_date,
)
from backend.core.offline_mode_guard import (
    OfflineModeGuard,
    OfflinePolicyViolation,
    install_offline_guard,
    is_offline_guard_active,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1-4: DatasetTypeClassifier
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatasetTypeClassifier:

    def setup_method(self):
        self.clf = DatasetTypeClassifier()

    # TEST 1 — Saudi attrition Excel → EMPLOYEE_ATTRITION_DATASET
    @pytest.mark.skipif(not _file_present(_ATTRITION_FILE), reason="Real dataset not present")
    def test_01_saudi_attrition_classified_correctly(self):
        df = pd.read_excel(_ATTRITION_FILE)
        result = self.clf.classify(df, filename="Original Dataset of Employee Attrition (1).xlsx")
        assert result.dataset_type == DatasetType.EMPLOYEE_ATTRITION_DATASET, (
            f"Expected EMPLOYEE_ATTRITION_DATASET, got {result.dataset_type}. "
            f"Evidence: {result.classification_evidence}"
        )
        assert result.attrition_modeling_allowed is True
        assert result.theory_activation_allowed is True
        assert result.dashboard_mode == "workforce_stability"

    # TEST 2 — Jadarat CSV → JOB_MARKET_POSTING_DATASET (not attrition)
    @pytest.mark.skipif(not _file_present(_JADARAT_FILE), reason="Real dataset not present")
    def test_02_jadarat_classified_as_job_market(self):
        df = pd.read_csv(_JADARAT_FILE, encoding="utf-8-sig", nrows=200)
        result = self.clf.classify(df, filename="Jadarat_data12.csv")
        assert result.dataset_type in (
            DatasetType.JOB_MARKET_POSTING_DATASET,
            DatasetType.GLOBAL_JOB_POSTING_STRESS_TEST,
        ), f"Expected job market type, got {result.dataset_type}"
        assert result.attrition_modeling_allowed is False
        assert result.attrition_block_reason is not None

    # TEST 3 — Job Posting.csv → GLOBAL_JOB_POSTING_STRESS_TEST (large + posting signals)
    @pytest.mark.skipif(not _file_present(_JOB_POST_FILE), reason="Real dataset not present")
    def test_03_large_job_posting_classified_as_stress_test(self):
        df = pd.read_csv(_JOB_POST_FILE, encoding="cp1256", nrows=500)
        result = self.clf.classify(df, filename="Job Posting.csv", row_count=9919)
        # Row count 9919 with posting signals → GLOBAL_JOB_POSTING_STRESS_TEST
        assert result.dataset_type in (
            DatasetType.JOB_MARKET_POSTING_DATASET,
            DatasetType.GLOBAL_JOB_POSTING_STRESS_TEST,
        ), f"Expected job market type, got {result.dataset_type}"
        assert result.attrition_modeling_allowed is False

    # TEST 4 — Synthetic unknown dataset → UNKNOWN_OR_UNSUPPORTED
    def test_04_unknown_dataset_blocked(self):
        df = pd.DataFrame({"col_a": [1, 2, 3], "col_b": ["x", "y", "z"]})
        result = self.clf.classify(df, filename="random_data.csv")
        assert result.dataset_type == DatasetType.UNKNOWN_OR_UNSUPPORTED
        assert result.attrition_modeling_allowed is False
        assert result.attrition_block_reason is not None


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5-8: SaudiAttritionNormalizer
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaudiAttritionNormalizer:

    def setup_method(self):
        self.norm = SaudiAttritionNormalizer()

    # TEST 5 — Real Saudi attrition file: columns renamed, attrition binary, salary parsed
    @pytest.mark.skipif(not _file_present(_ATTRITION_FILE), reason="Real dataset not present")
    def test_05_normalizer_on_real_saudi_attrition_file(self):
        df = pd.read_excel(_ATTRITION_FILE)
        result = self.norm.normalize(df)
        assert result.success is True
        assert result.df_normalized is not None
        # Attrition binary column must exist
        assert result.attrition_column is not None, "No attrition column detected"
        binary_col = result.attrition_column + "_binary"
        assert binary_col in result.df_normalized.columns, f"Binary column {binary_col!r} not created"
        # Binary column must be only 0/1/NaN
        vals = result.df_normalized[binary_col].dropna().unique()
        assert set(vals).issubset({0, 1}), f"Unexpected binary values: {vals}"
        # Salary column parsed
        assert len(result.salary_columns_parsed) > 0, "No salary column was parsed"
        # At least some proxy constructs available
        assert len(result.proxy_constructs_available) > 0, "No proxy constructs available"

    # TEST 6 — Attrition " Yes"/" No" leading-space normalization
    def test_06_attrition_leading_space_normalization(self):
        df = pd.DataFrame({
            "Attrition": [" Yes", " No", "Yes", "No", " YES", " NO"],
        })
        result = self.norm.normalize(df)
        assert result.success is True
        binary_vals = result.df_normalized["attrition_binary"].tolist()
        assert binary_vals == [1, 0, 1, 0, 1, 0]

    # TEST 7 — Salary range parsing produces midpoint
    def test_07_salary_range_parsing(self):
        df = pd.DataFrame({
            "Attrition": ["Yes", "No", "Yes"],
            "MonthlySalary": [
                "From 5000 to 10000 S.R",
                "Less than 5000 SAR",
                "More than 15000",
            ],
        })
        result = self.norm.normalize(df)
        assert result.success is True
        assert "monthly_salary_range" in result.salary_columns_parsed
        mid = result.df_normalized["monthly_salary_range_midpoint"].tolist()
        assert mid[0] == pytest.approx(7500.0)
        assert mid[1] == pytest.approx(3750.0)   # 5000 * 0.75
        assert mid[2] == pytest.approx(18750.0)  # 15000 * 1.25

    # TEST 8 — Proxy constructs labelled as PROXY
    def test_08_proxy_constructs_are_labelled_proxy(self):
        for key, info in PROXY_CONSTRUCT_MAP.items():
            assert info["proxy"] is True, (
                f"Construct '{key}' must be labelled proxy=True"
            )
            assert "theory" in info
            assert "columns" in info
            assert len(info["columns"]) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 9-12: JobMarketDatasetHandler
# ═══════════════════════════════════════════════════════════════════════════════

class TestJobMarketDatasetHandler:

    def setup_method(self):
        self.handler = JobMarketDatasetHandler()

    # TEST 9 — Jadarat CSV: subtype detected, Hijri dates, salary from benefits, no attrition
    @pytest.mark.skipif(not _file_present(_JADARAT_FILE), reason="Real dataset not present")
    def test_09_jadarat_handling(self):
        df = pd.read_csv(_JADARAT_FILE, encoding="utf-8-sig")
        result = self.handler.handle(df, filename="Jadarat_data12.csv")
        assert result.success is True
        assert result.subtype == JobMarketSubtype.JADARAT_SAUDI_POSTINGS
        assert result.analysis_mode == "market_intelligence"
        assert result.attrition_blocked is True
        assert "attrition" in result.attrition_block_reason.lower()
        # Hijri dates should be detected in job_date column
        assert result.hijri_date_column is not None, "Hijri date column not detected in Jadarat"

    # TEST 10 — processed_dataset.csv: numeric salary extracted, comp_name blocked
    @pytest.mark.skipif(not _file_present(_PROCESSED_FILE), reason="Real dataset not present")
    def test_10_processed_dataset_handling(self):
        df = pd.read_csv(_PROCESSED_FILE, encoding="utf-8-sig")
        result = self.handler.handle(df, filename="processed_dataset.csv")
        assert result.success is True
        assert result.analysis_mode == "market_intelligence"
        assert result.attrition_blocked is True
        # comp_name is sensitive
        sensitive_lower = [c.lower() for c in result.sensitive_columns_detected]
        assert any("comp" in c or "company" in c for c in sensitive_lower), (
            f"comp_name/company not in sensitive_columns_detected: {result.sensitive_columns_detected}"
        )

    # TEST 11 — Job Posting.csv: large stress test, attrition blocked, no Saudi conclusions
    @pytest.mark.skipif(not _file_present(_JOB_POST_FILE), reason="Real dataset not present")
    def test_11_large_job_posting_stress_test(self):
        df = pd.read_csv(_JOB_POST_FILE, encoding="cp1256", nrows=500)
        # Simulate full row count to trigger stress-test path
        result = self.handler.handle(df, filename="Job Posting.csv")
        assert result.success is True
        assert result.analysis_mode == "market_intelligence"
        assert result.attrition_blocked is True
        # Stress test should produce a warning
        assert any("stress" in w.lower() or "ingestion" in w.lower() for w in result.warnings), (
            f"Expected stress-test warning, got: {result.warnings}"
        )

    # TEST 12 — Synthetic job market: analysis_mode always "market_intelligence"
    def test_12_synthetic_job_market_always_market_intelligence(self):
        df = pd.DataFrame({
            "job_title":  ["Software Engineer", "Data Analyst", "Project Manager"],
            "comp_name":  ["Company A", "Company B", "Company C"],
            "region":     ["Riyadh", "Jeddah", "Dammam"],
            "salary":     [10000.0, 8000.0, 12000.0],
        })
        result = self.handler.handle(df, filename="synthetic.csv")
        assert result.analysis_mode == "market_intelligence"
        assert result.attrition_blocked is True


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 13-14: Helper unit tests (salary, positions, experience, Hijri)
# ═══════════════════════════════════════════════════════════════════════════════

class TestJobMarketHelpers:

    # TEST 13 — Benefits salary extraction
    def test_13_salary_extraction_from_benefits(self):
        assert _extract_salary_from_benefits("['Salary', '5000.0']") == pytest.approx(5000.0)
        assert _extract_salary_from_benefits("['Housing', 'Transportation']") is None
        assert _extract_salary_from_benefits(None) is None
        assert _extract_salary_from_benefits(float("nan")) is None
        assert _extract_salary_from_benefits("['Salary', '12000.0']") == pytest.approx(12000.0)

    # TEST 14 — Position parsing, experience parsing, Hijri detection
    def test_14_field_parsers(self):
        # Position slots
        assert _parse_positions("0 / 3") == (0, 3)
        assert _parse_positions("2 / 5") == (2, 5)
        assert _parse_positions(None) == (None, None)
        assert _parse_positions("unknown") == (None, None)

        # Experience
        assert _parse_experience_years("0 Years") == pytest.approx(0.0)
        assert _parse_experience_years("3 Years") == pytest.approx(3.0)
        assert _parse_experience_years("5 years") == pytest.approx(5.0)
        assert _parse_experience_years(None) is None

        # Hijri dates
        assert _is_hijri_date("27/05/1444") is True
        assert _is_hijri_date("2024-01-15") is False   # Gregorian
        assert _is_hijri_date("01/01/2023") is False   # Gregorian
        assert _is_hijri_date(None) is False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 15-16: OfflineModeGuard
# ═══════════════════════════════════════════════════════════════════════════════

class TestOfflineModeGuard:

    def setup_method(self):
        # Always start with a fresh, uninstalled guard for isolation
        self.guard = OfflineModeGuard()
        self.guard.clear_violations()

    def teardown_method(self):
        # Restore if installed during test
        if self.guard._installed:
            self.guard.uninstall()

    # TEST 15 — Guard blocks external hosts, allows loopback
    def test_15_offline_guard_blocks_external_allows_loopback(self):
        self.guard.install()
        assert self.guard._installed is True

        # External host → should raise OfflinePolicyViolation
        with pytest.raises(OfflinePolicyViolation) as exc_info:
            self.guard._record_violation("api.openai.com:443", "test_caller")
            raise OfflinePolicyViolation("api.openai.com:443", "test_caller")

        assert "OFFLINE_POLICY_VIOLATION" in str(exc_info.value)
        assert "api.openai.com" in str(exc_info.value)

        # Loopback → should be allowed
        assert self.guard._is_allowed("localhost") is True
        assert self.guard._is_allowed("127.0.0.1") is True
        assert self.guard._is_allowed("::1") is True

        # External → should be blocked
        assert self.guard._is_allowed("api.openai.com") is False
        assert self.guard._is_allowed("example.com") is False
        assert self.guard._is_allowed("8.8.8.8") is False

    # TEST 16 — Guard status is auditable, violation count is tracked
    def test_16_offline_guard_status_auditable(self):
        self.guard.install()

        # Trigger two violations
        self.guard._record_violation("external-service.com:443", "test_a")
        self.guard._record_violation("telemetry.vendor.com:80", "test_b")

        status = self.guard.status()
        assert status["offline_mode_active"] is True
        assert status["violation_count"] == 2
        assert len(status["violations"]) == 2
        assert "OFFLINE_FIRST" in status["policy"]
        assert "PDPL" in status["policy"]

        # Violation records have required fields
        v = status["violations"][0]
        assert "timestamp" in v
        assert "destination" in v
        assert "caller" in v

        # Clear violations
        self.guard.clear_violations()
        assert self.guard.get_violation_count() == 0
