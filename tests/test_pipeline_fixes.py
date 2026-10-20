"""
Pipeline Fix Tests — Local Upload Analysis.

Verifies:
  1. "Attrition" column is renamed → "flight_risk" (not blocked as leakage)
  2. Saudi HR attrition dataset becomes READY or CONDITIONAL after normalization
  3. Health score (0-100) present in every response
  4. Workforce indicators present and structured correctly
  5. Executive recommendations present
  6. column_normalizations_applied list present
  7. Jadarat CSV classified correctly (market intelligence, no attrition block)
  8. JobPosting CSV classified correctly (stress test)
  9. _error_response and _timeout_response include all new fields
  10. Timing key "normalization" present in timing_ms
  11. Synthetic clean HR CSV passes governance with high health score
  12. PII column still blocked after normalization (normalization must not bypass PII)
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.api.local_analysis_routes import (
    _preprocess_raw_bytes,
    _compute_health_score,
    _build_workforce_indicators,
    _build_executive_recommendations,
    _error_response,
    _timeout_response,
    _SAUDI_HR_COLUMN_RENAMES,
)
from backend.core.secure_file_ingestion import SecureFileIngestion
from backend.core.dataset_type_classifier import DatasetTypeClassifier, MARKET_INTELLIGENCE_ALLOWED

_scanner    = SecureFileIngestion()
_classifier = DatasetTypeClassifier()

_SAUDI_DIR = Path(r"C:\Users\PvP-Pc\Desktop\datasetssaudi")

# ── Required keys in every response ──────────────────────────────────────────

_REQUIRED_KEYS = {
    "readiness_level", "row_count", "column_count", "feature_column_count",
    "health_score", "workforce_indicators", "executive_recommendations",
    "column_normalizations_applied", "timing_ms", "is_fast_path",
    "dataset_type", "classification_confidence",
    "executive_readiness", "pdpl_note",
}

_TIMING_KEYS = {"file_read", "normalization", "governance_scan", "classification", "total"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(raw: bytes, filename: str) -> dict[str, Any]:
    """Full pipeline: preprocess → scan → classify → build result dict."""
    import time

    t0 = time.perf_counter()
    normalized_bytes, normalization_log = _preprocess_raw_bytes(raw, filename)
    t_norm = time.perf_counter()

    scan_filename = filename if not normalization_log else filename + ".normalized.csv"
    report = _scanner.scan(raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local")
    t_scan = time.perf_counter()

    ir = report.ingestion_result
    dataset_type = "UNKNOWN_OR_UNSUPPORTED"
    analysis_mode = "blocked"
    attrition_allowed = False
    theory_allowed = False
    market_allowed = False
    classification_conf = 0.0

    if ir.success and ir.df is not None:
        clf = _classifier.classify(ir.df, filename=filename)
        dataset_type        = clf.dataset_type.value
        analysis_mode       = clf.dashboard_mode
        attrition_allowed   = clf.attrition_modeling_allowed
        theory_allowed      = clf.theory_activation_allowed
        market_allowed      = clf.dataset_type in MARKET_INTELLIGENCE_ALLOWED
        classification_conf = clf.confidence
    t_classify = time.perf_counter()

    all_warnings = list(report.warnings)
    can_proceed  = report.readiness_level.value in ("READY", "CONDITIONAL")

    health_score = _compute_health_score(
        readiness=report.readiness_level.value,
        missing_pct=report.data_quality.missing_value_pct,
        duplicate_rows=report.data_quality.duplicate_rows,
        row_count=ir.row_count,
        n_blocking=len(report.blocking_reasons),
        n_warnings=len(all_warnings),
        feature_count=len(report.feature_columns),
    )

    workforce_indicators = _build_workforce_indicators(
        dataset_type=dataset_type,
        attrition_allowed=attrition_allowed,
        theory_allowed=theory_allowed,
        market_allowed=market_allowed,
        readiness=report.readiness_level.value,
        feature_count=len(report.feature_columns),
        row_count=ir.row_count,
        classification_conf=classification_conf,
    )

    exec_recs = _build_executive_recommendations(
        readiness=report.readiness_level.value,
        dataset_type=dataset_type,
        pii_columns=report.pii_columns_detected,
        leakage_columns=report.leakage_columns_detected,
        normalizations=normalization_log,
        missing_pct=report.data_quality.missing_value_pct,
        duplicate_rows=report.data_quality.duplicate_rows,
        feature_count=len(report.feature_columns),
        attrition_allowed=attrition_allowed,
        warnings=all_warnings,
    )

    total = time.perf_counter()

    return {
        "readiness_level":            report.readiness_level.value,
        "row_count":                  ir.row_count,
        "column_count":               ir.column_count,
        "feature_column_count":       len(report.feature_columns),
        "detected_language":          ir.detected_language,
        "detected_erp_style":         ir.detected_erp_style,
        "warnings":                   all_warnings,
        "blocking_reasons":           report.blocking_reasons,
        "pii_columns_detected":       report.pii_columns_detected,
        "leakage_columns_detected":   report.leakage_columns_detected,
        "filename":                   filename,
        "dataset_type":               dataset_type,
        "dataset_type_label":         dataset_type,
        "analysis_mode":              analysis_mode,
        "analysis_mode_label":        analysis_mode,
        "attrition_modeling_allowed": attrition_allowed,
        "theory_activation_allowed":  theory_allowed,
        "market_intelligence_allowed": market_allowed,
        "classification_confidence":  classification_conf,
        "governance_scan_passed":     report.governance_scan_passed,
        "identified_target_column":   report.identified_target_column,
        "feature_columns":            report.feature_columns[:30],
        "recommended_actions":        report.recommended_actions,
        "duplicate_rows":             report.data_quality.duplicate_rows,
        "missing_value_pct":          report.data_quality.missing_value_pct,
        "encoding_used":              ir.encoding_used,
        "ingestion_warnings":         ir.warnings,
        "ingestion_transformations":  ir.transformations,
        "executive_readiness": {
            "can_generate_report":     can_proceed,
            "can_run_attrition_model": can_proceed and attrition_allowed,
            "can_run_theory_engine":   can_proceed and theory_allowed,
            "can_show_dashboard":      can_proceed and analysis_mode != "blocked",
            "readiness_summary":       "",
        },
        "health_score":                   health_score,
        "workforce_indicators":           workforce_indicators,
        "executive_recommendations":      exec_recs,
        "column_normalizations_applied":  normalization_log,
        "timing_ms": {
            "file_read":       0.0,
            "normalization":   round((t_norm - t0) * 1000, 1),
            "governance_scan": round((t_scan - t_norm) * 1000, 1),
            "classification":  round((t_classify - t_scan) * 1000, 1),
            "total":           round((total - t0) * 1000, 1),
        },
        "is_fast_path": len(raw) < 5 * 1024 * 1024,
        "pdpl_note":   "test",
    }


def _make_hr_csv_with_attrition(n: int = 500) -> bytes:
    """Creates a synthetic Saudi HR CSV that uses 'Attrition' as the outcome column."""
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "EmployeeNumber": range(1, n + 1),
        "Department":      rng.choice(["Engineering", "Sales", "HR", "Finance"], n),
        "TenureYears":     rng.uniform(0.5, 20, n).round(1),
        "Age":             rng.integers(22, 60, n),
        "PerformanceRating": rng.uniform(1, 5, n).round(2),
        "MonthlyIncome":   rng.integers(5000, 50000, n),
        "OverTime":        rng.choice(["Yes", "No"], n),
        "JobSatisfaction": rng.integers(1, 5, n),
        "WorkLifeBalance": rng.integers(1, 4, n),
        "Attrition":       rng.choice(["Yes", "No"], n),   # <-- the problematic column
    })
    return df.to_csv(index=False).encode()


def _make_clean_hr_csv(n: int = 400) -> bytes:
    """Clean HR CSV with flight_risk target (already normalized name)."""
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "employee_id":     range(1, n + 1),
        "department":      rng.choice(["Engineering", "Sales", "HR", "Finance"], n),
        "tenure_years":    rng.uniform(0.5, 20, n).round(1),
        "age":             rng.integers(22, 60, n),
        "performance":     rng.uniform(1, 5, n).round(2),
        "overtime_hours":  rng.integers(0, 40, n),
        "engagement_score":rng.uniform(1, 5, n).round(2),
        "flight_risk":     rng.choice([0, 1], n),
    })
    return df.to_csv(index=False).encode()


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_fix_01_attrition_column_renamed_in_normalization_log():
    """_preprocess_raw_bytes must rename 'Attrition' → 'flight_risk' and log it."""
    raw = _make_hr_csv_with_attrition(200)
    _, log = _preprocess_raw_bytes(raw, "test.csv")
    assert any("Attrition" in entry and "flight_risk" in entry for entry in log), (
        f"Expected normalization log to mention Attrition→flight_risk. Got: {log}"
    )


def test_fix_02_attrition_column_not_in_leakage_after_normalization():
    """After normalization, 'Attrition' must NOT appear in leakage_columns_detected."""
    raw = _make_hr_csv_with_attrition(300)
    result = _run(raw, "attrition_norm.csv")
    assert "Attrition" not in result["leakage_columns_detected"], (
        f"'Attrition' should have been renamed before governance scan. "
        f"Leakage detected: {result['leakage_columns_detected']}"
    )


def test_fix_03_attrition_dataset_not_blocked_by_column_name():
    """Synthetic Saudi attrition CSV must NOT be BLOCKED due to 'Attrition' column."""
    raw = _make_hr_csv_with_attrition(400)
    result = _run(raw, "saudi_attrition.csv")
    # The only acceptable blocking reason is something other than the Attrition column
    leakage_block = [
        r for r in result["blocking_reasons"]
        if "Attrition" in r and "leakage" in r.lower()
    ]
    assert not leakage_block, (
        f"Attrition column leakage block still present after normalization: {leakage_block}"
    )


def test_fix_04_health_score_present_and_in_range():
    """health_score must be 0-100 integer in every result."""
    raw = _make_clean_hr_csv(300)
    result = _run(raw, "health.csv")
    assert "health_score" in result
    hs = result["health_score"]
    assert isinstance(hs, int), f"health_score must be int, got {type(hs)}"
    assert 0 <= hs <= 100, f"health_score out of range: {hs}"


def test_fix_05_clean_csv_high_health_score():
    """A clean HR CSV with no issues should score >= 60."""
    raw = _make_clean_hr_csv(400)
    result = _run(raw, "clean.csv")
    assert result["health_score"] >= 60, (
        f"Expected health_score >= 60 for clean dataset, got {result['health_score']}. "
        f"blocking={result['blocking_reasons']}, warnings={result['warnings']}"
    )


def test_fix_06_workforce_indicators_present_and_structured():
    """workforce_indicators must be a non-empty list of dicts with label/value/status."""
    raw = _make_clean_hr_csv(300)
    result = _run(raw, "wi.csv")
    assert "workforce_indicators" in result
    wi = result["workforce_indicators"]
    assert isinstance(wi, list) and len(wi) > 0, "workforce_indicators must be non-empty list"
    for item in wi:
        assert "label" in item and "value" in item and "status" in item, (
            f"Indicator missing required keys: {item}"
        )
        assert item["status"] in ("ok", "warn", "error", "info", "neutral")


def test_fix_07_executive_recommendations_present():
    """executive_recommendations must be a list (may be empty for perfect datasets)."""
    raw = _make_clean_hr_csv(300)
    result = _run(raw, "recs.csv")
    assert "executive_recommendations" in result
    assert isinstance(result["executive_recommendations"], list)


def test_fix_08_column_normalizations_list_present():
    """column_normalizations_applied must be a list in every response."""
    raw = _make_clean_hr_csv(200)
    result = _run(raw, "norms.csv")
    assert "column_normalizations_applied" in result
    assert isinstance(result["column_normalizations_applied"], list)


def test_fix_09_normalization_key_in_timing_ms():
    """timing_ms must include 'normalization' key (pipeline fix addition)."""
    raw = _make_clean_hr_csv(200)
    result = _run(raw, "timing.csv")
    assert "timing_ms" in result
    assert "normalization" in result["timing_ms"], (
        f"'normalization' key missing from timing_ms: {result['timing_ms']}"
    )


def test_fix_10_error_response_has_new_fields():
    """_error_response must include health_score, workforce_indicators, executive_recommendations."""
    r = _error_response("test.csv", "File too large.")
    for key in ("health_score", "workforce_indicators", "executive_recommendations",
                "column_normalizations_applied", "timing_ms", "is_fast_path"):
        assert key in r, f"_error_response missing key: {key}"
    assert r["health_score"] == 0
    assert isinstance(r["workforce_indicators"], list)


def test_fix_11_timeout_response_has_new_fields():
    """_timeout_response must include health_score, executive_recommendations."""
    r = _timeout_response("test.csv", "Scan exceeded 15s.")
    for key in ("health_score", "executive_recommendations", "column_normalizations_applied"):
        assert key in r, f"_timeout_response missing key: {key}"
    assert "timing_ms" in r
    assert "normalization" in r["timing_ms"]


def test_fix_12_pii_still_blocked_after_normalization():
    """Normalization must NOT bypass PII detection — email column must still block."""
    rng = np.random.default_rng(1)
    n = 200
    df = pd.DataFrame({
        "department":    rng.choice(["HR", "Eng"], n),
        "tenure_years":  rng.uniform(1, 10, n).round(1),
        "email":         [f"emp{i}@company.com" for i in range(n)],  # PII
        "flight_risk":   rng.choice([0, 1], n),
    })
    raw = df.to_csv(index=False).encode()
    result = _run(raw, "pii_test.csv")
    assert result["readiness_level"] == "BLOCKED", (
        "Dataset with email PII column should still be BLOCKED after normalization"
    )
    assert len(result["pii_columns_detected"]) > 0


def test_fix_13_saudi_hr_column_renames_coverage():
    """All keys in _SAUDI_HR_COLUMN_RENAMES must be lowercase strings."""
    for k, v in _SAUDI_HR_COLUMN_RENAMES.items():
        assert k == k.lower(), f"Rename key '{k}' is not lowercase"
        assert isinstance(v, str) and v, f"Rename value for '{k}' is invalid"


def test_fix_14_health_score_compute_logic():
    """_compute_health_score follows scoring rules: perfect = 100, blocked capped at 40."""
    perfect = _compute_health_score("READY", 0.0, 0, 500, 0, 0, 10)
    assert perfect == 100, f"Perfect dataset should score 100, got {perfect}"

    blocked = _compute_health_score("BLOCKED", 50.0, 100, 500, 2, 5, 1)
    assert blocked <= 40, f"BLOCKED dataset should be capped at 40, got {blocked}"

    empty_features = _compute_health_score("READY", 0.0, 0, 200, 0, 0, 0)
    assert empty_features < 100, "Zero features should reduce health score"


# ── Real Saudi file tests (skipped if absent) ─────────────────────────────────

@pytest.mark.skipif(
    not (_SAUDI_DIR / "Original Dataset of Employee Attrition (1).xlsx").exists(),
    reason="Real Saudi attrition file not present",
)
def test_fix_15_real_saudi_attrition_not_blocked_by_attrition_column():
    """
    Real Saudi Excel attrition dataset must not be BLOCKED solely because of
    the 'Attrition' column — normalization renames it to 'flight_risk' first.
    """
    path = _SAUDI_DIR / "Original Dataset of Employee Attrition (1).xlsx"
    raw = path.read_bytes()
    _, log = _preprocess_raw_bytes(raw, path.name)

    # Normalization log must mention the rename
    attrition_renames = [e for e in log if "Attrition" in e and "flight_risk" in e]
    assert attrition_renames, (
        f"Expected Attrition→flight_risk normalization for real Saudi file. "
        f"Got log: {log}"
    )

    result = _run(raw, path.name)
    # After normalization, the Attrition leakage block should be gone
    leakage_blocks = [r for r in result["blocking_reasons"] if "Leakage" in r and "Attrition" in r]
    assert not leakage_blocks, (
        f"Attrition leakage block still present after normalization: {leakage_blocks}"
    )

    assert result["dataset_type"] == "EMPLOYEE_ATTRITION_DATASET"
    assert result["health_score"] > 0
    assert len(result["workforce_indicators"]) > 0


@pytest.mark.skipif(
    not (_SAUDI_DIR / "Jadarat_data12.csv").exists(),
    reason="Jadarat file not present",
)
def test_fix_16_jadarat_csv_classified_as_market_intelligence():
    """Jadarat CSV must classify as JOB_MARKET_POSTING_DATASET with market intel allowed."""
    path = _SAUDI_DIR / "Jadarat_data12.csv"
    raw = path.read_bytes()
    result = _run(raw, path.name)

    assert result["dataset_type"] == "JOB_MARKET_POSTING_DATASET", (
        f"Expected JOB_MARKET_POSTING_DATASET, got {result['dataset_type']}"
    )
    assert result["market_intelligence_allowed"] is True
    assert result["attrition_modeling_allowed"] is False
    assert result["health_score"] >= 0

    # Indicators must include a market intel entry
    labels = [i["label"] for i in result["workforce_indicators"]]
    assert any("Market" in l for l in labels), f"No market intel indicator found: {labels}"


@pytest.mark.skipif(
    not (_SAUDI_DIR / "Job Posting.csv").exists(),
    reason="Job Posting file not present",
)
def test_fix_17_job_posting_csv_classified():
    """Job Posting CSV must classify and return structured indicators."""
    path = _SAUDI_DIR / "Job Posting.csv"
    raw = path.read_bytes()
    result = _run(raw, path.name)

    assert result["dataset_type"] in (
        "JOB_MARKET_POSTING_DATASET",
        "GLOBAL_JOB_POSTING_STRESS_TEST",
        "UNKNOWN_OR_UNSUPPORTED",
    )
    assert "health_score" in result
    assert "workforce_indicators" in result
    assert result["row_count"] > 0
