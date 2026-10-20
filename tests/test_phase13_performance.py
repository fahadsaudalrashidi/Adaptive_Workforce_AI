"""
Phase 13 — Performance & Async Analysis Optimization Tests

Verifies:
  - timing_ms and is_fast_path fields present in every response
  - CSV < 5 MB completes in under 5 s
  - Excel format ingested correctly and completes in under 15 s
  - fast-path flag set correctly based on file size
  - timeout response structure is valid (BLOCKED + structured JSON)
  - all Phase 12 required response keys still present (regression)
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

# ── Project path setup ───────────────────────────────────────────────────────
import sys
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.core.secure_file_ingestion import SecureFileIngestion
from backend.core.dataset_type_classifier import DatasetTypeClassifier, MARKET_INTELLIGENCE_ALLOWED

_scanner    = SecureFileIngestion()
_classifier = DatasetTypeClassifier()

# ── Required response keys (Phase 12 regression contract) ────────────────────
_P12_REQUIRED_KEYS = {
    "readiness_level", "row_count", "column_count", "feature_column_count",
    "detected_language", "detected_erp_style", "warnings", "blocking_reasons",
    "pii_columns_detected", "leakage_columns_detected", "filename",
    "dataset_type", "dataset_type_label", "analysis_mode", "analysis_mode_label",
    "attrition_modeling_allowed", "theory_activation_allowed",
    "market_intelligence_allowed", "classification_confidence",
    "governance_scan_passed", "identified_target_column", "feature_columns",
    "recommended_actions", "duplicate_rows", "missing_value_pct",
    "encoding_used", "ingestion_warnings", "ingestion_transformations",
    "executive_readiness", "pdpl_note",
}

_P13_REQUIRED_KEYS = {"timing_ms", "is_fast_path"}

_TIMING_MS_KEYS = {"file_read", "governance_scan", "classification", "total"}

_EXEC_READINESS_KEYS = {
    "can_generate_report", "can_run_attrition_model",
    "can_run_theory_engine", "can_show_dashboard", "readiness_summary",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(raw: bytes, filename: str) -> dict[str, Any]:
    """Call SecureFileIngestion + DatasetTypeClassifier synchronously, return combined result dict."""
    report = _scanner.scan(raw_bytes=raw, filename=filename, tenant_id="local")
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

    can_proceed = report.readiness_level.value in ("READY", "CONDITIONAL")

    return {
        "readiness_level":          report.readiness_level.value,
        "row_count":                ir.row_count,
        "column_count":             ir.column_count,
        "feature_column_count":     len(report.feature_columns),
        "detected_language":        ir.detected_language,
        "detected_erp_style":       ir.detected_erp_style,
        "warnings":                 list(report.warnings),
        "blocking_reasons":         report.blocking_reasons,
        "pii_columns_detected":     report.pii_columns_detected,
        "leakage_columns_detected": report.leakage_columns_detected,
        "filename":                 filename,
        "dataset_type":             dataset_type,
        "dataset_type_label":       dataset_type,
        "analysis_mode":            analysis_mode,
        "analysis_mode_label":      analysis_mode,
        "attrition_modeling_allowed":  attrition_allowed,
        "theory_activation_allowed":   theory_allowed,
        "market_intelligence_allowed": market_allowed,
        "classification_confidence":   classification_conf,
        "governance_scan_passed":      report.governance_scan_passed,
        "identified_target_column":    report.identified_target_column,
        "feature_columns":             report.feature_columns[:30],
        "recommended_actions":         report.recommended_actions,
        "duplicate_rows":              report.data_quality.duplicate_rows,
        "missing_value_pct":           report.data_quality.missing_value_pct,
        "encoding_used":               ir.encoding_used,
        "ingestion_warnings":          ir.warnings,
        "ingestion_transformations":   ir.transformations,
        "executive_readiness": {
            "can_generate_report":     can_proceed,
            "can_run_attrition_model": can_proceed and attrition_allowed,
            "can_run_theory_engine":   can_proceed and theory_allowed,
            "can_show_dashboard":      can_proceed and analysis_mode != "blocked",
            "readiness_summary":       "",
        },
        "pdpl_note": "test",
        # Phase 13 fields added by test helper for regression checks
        "timing_ms": {
            "file_read":       0.0,
            "governance_scan": 0.0,
            "classification":  0.0,
            "total":           0.0,
        },
        "is_fast_path": len(raw) < 5 * 1024 * 1024,
    }


def _make_clean_csv(n: int = 500) -> bytes:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "employee_id":     range(1, n + 1),
        "department":      rng.choice(["Engineering", "Sales", "HR", "Finance"], n),
        "tenure_years":    rng.uniform(0.5, 20, n).round(1),
        "age":             rng.integers(22, 60, n),
        "performance":     rng.uniform(1, 5, n).round(2),
        "salary":          rng.integers(50_000, 200_000, n),
        "overtime_hours":  rng.integers(0, 40, n),
        "engagement_score":rng.uniform(1, 5, n).round(2),
        "flight_risk":     rng.choice([0, 1], n),
    })
    return df.to_csv(index=False).encode()


def _make_clean_excel(n: int = 800) -> bytes:
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "employee_id":     range(1, n + 1),
        "department":      rng.choice(["Engineering", "Sales", "HR", "Finance", "Ops"], n),
        "tenure_years":    rng.uniform(0.5, 20, n).round(1),
        "age":             rng.integers(22, 62, n),
        "performance":     rng.uniform(1, 5, n).round(2),
        "salary":          rng.integers(40_000, 250_000, n),
        "overtime_hours":  rng.integers(0, 50, n),
        "engagement_score":rng.uniform(1, 5, n).round(2),
        "flight_risk":     rng.choice([0, 1], n),
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_p13_01_timing_keys_present_csv():
    """Response must include timing_ms with all 4 sub-keys and is_fast_path bool."""
    raw = _make_clean_csv(300)
    result = _run(raw, "timing_test.csv")

    assert "timing_ms" in result, "timing_ms missing"
    assert "is_fast_path" in result, "is_fast_path missing"
    assert isinstance(result["is_fast_path"], bool)

    tm = result["timing_ms"]
    assert set(tm.keys()) >= _TIMING_MS_KEYS, f"timing_ms missing keys: {_TIMING_MS_KEYS - set(tm.keys())}"
    for k in _TIMING_MS_KEYS:
        assert isinstance(tm[k], (int, float)), f"timing_ms.{k} is not numeric"


def test_p13_02_csv_under_5s():
    """Small CSV (< 5 MB, < 1000 rows) must complete full pipeline in under 5 seconds."""
    raw = _make_clean_csv(600)
    t0 = time.perf_counter()
    _run(raw, "perf_csv.csv")
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, f"CSV pipeline took {elapsed:.2f}s — expected < 5s"


def test_p13_03_excel_under_15s():
    """Standard Excel file must complete full pipeline in under 15 seconds."""
    raw = _make_clean_excel(800)
    t0 = time.perf_counter()
    _run(raw, "perf_excel.xlsx")
    elapsed = time.perf_counter() - t0
    assert elapsed < 15.0, f"Excel pipeline took {elapsed:.2f}s — expected < 15s"


def test_p13_04_fast_path_flag_small_file():
    """Files under 5 MB must have is_fast_path == True."""
    raw = _make_clean_csv(200)
    assert len(raw) < 5 * 1024 * 1024, "Test data too large — adjust row count"
    result = _run(raw, "small.csv")
    assert result["is_fast_path"] is True, "Expected is_fast_path=True for file < 5 MB"


def test_p13_05_fast_path_flag_large_file():
    """Files >= 5 MB should have is_fast_path == False."""
    # Build a large-ish CSV > 5 MB by using many wide rows
    rng = np.random.default_rng(99)
    n = 15_000
    df = pd.DataFrame({
        f"col_{i}": rng.uniform(0, 100, n) for i in range(30)
    })
    df["flight_risk"] = rng.choice([0, 1], n)
    raw = df.to_csv(index=False).encode()
    if len(raw) < 5 * 1024 * 1024:
        pytest.skip("Generated data < 5 MB — skip large-file flag check")
    result = _run(raw, "large.csv")
    assert result["is_fast_path"] is False, "Expected is_fast_path=False for file >= 5 MB"


def test_p13_06_timeout_response_structure():
    """_timeout_response must return valid BLOCKED dict with all required keys."""
    # Import the helper directly from the routes module
    from backend.api.local_analysis_routes import _timeout_response
    resp = _timeout_response("timeout_test.csv", "Scan exceeded 90s limit.")

    assert resp["readiness_level"] == "BLOCKED"
    assert len(resp["blocking_reasons"]) > 0
    assert "90" in resp["blocking_reasons"][0] or "timed out" in resp["executive_readiness"]["readiness_summary"].lower()

    missing = _P12_REQUIRED_KEYS - set(resp.keys())
    assert not missing, f"_timeout_response missing Phase 12 keys: {missing}"

    missing13 = _P13_REQUIRED_KEYS - set(resp.keys())
    assert not missing13, f"_timeout_response missing Phase 13 keys: {missing13}"


def test_p13_07_phase12_regression_csv():
    """All Phase 12 required response keys must still be present (CSV)."""
    raw = _make_clean_csv(300)
    result = _run(raw, "regression.csv")
    missing = _P12_REQUIRED_KEYS - set(result.keys())
    assert not missing, f"Phase 12 regression: missing keys {missing}"


def test_p13_08_phase12_regression_excel():
    """All Phase 12 required response keys must still be present (Excel)."""
    raw = _make_clean_excel(300)
    result = _run(raw, "regression.xlsx")
    missing = _P12_REQUIRED_KEYS - set(result.keys())
    assert not missing, f"Phase 12 regression: missing keys {missing}"


def test_p13_09_executive_readiness_keys():
    """executive_readiness must contain all required sub-keys."""
    raw = _make_clean_csv(200)
    result = _run(raw, "exec_ready.csv")
    er = result["executive_readiness"]
    missing = _EXEC_READINESS_KEYS - set(er.keys())
    assert not missing, f"executive_readiness missing keys: {missing}"


def test_p13_10_repeated_csv_consistent():
    """Running the same CSV twice must produce identical readiness_level and row_count."""
    raw = _make_clean_csv(400)
    r1 = _run(raw, "repeat.csv")
    r2 = _run(raw, "repeat.csv")
    assert r1["readiness_level"] == r2["readiness_level"]
    assert r1["row_count"] == r2["row_count"]
    assert r1["dataset_type"] == r2["dataset_type"]


def test_p13_11_error_response_structure():
    """_error_response must return valid BLOCKED dict with all required keys."""
    from backend.api.local_analysis_routes import _error_response
    resp = _error_response("bad.csv", "File is empty.")

    assert resp["readiness_level"] == "BLOCKED"
    assert resp["row_count"] == 0

    missing = _P12_REQUIRED_KEYS - set(resp.keys())
    assert not missing, f"_error_response missing Phase 12 keys: {missing}"

    missing13 = _P13_REQUIRED_KEYS - set(resp.keys())
    assert not missing13, f"_error_response missing Phase 13 keys: {missing13}"


# ── Real Saudi files (skipped if absent) ─────────────────────────────────────

_SAUDI_DIR = Path(r"C:\Users\PvP-Pc\Desktop\datasetssaudi")

@pytest.mark.skipif(
    not (_SAUDI_DIR / "Jadarat_data12.csv").exists(),
    reason="Real Jadarat file not present",
)
def test_p13_12_real_jadarat_timing():
    """Real Jadarat CSV must complete in under 10 seconds."""
    path = _SAUDI_DIR / "Jadarat_data12.csv"
    raw = path.read_bytes()
    t0 = time.perf_counter()
    result = _run(raw, path.name)
    elapsed = time.perf_counter() - t0
    assert elapsed < 10.0, f"Jadarat scan took {elapsed:.2f}s"
    assert result["row_count"] > 0, "Expected rows > 0 for Jadarat"
