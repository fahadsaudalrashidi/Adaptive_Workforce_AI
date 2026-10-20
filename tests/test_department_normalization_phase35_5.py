"""
Phase 35.5 (correction) — Department name normalization tests.

Covers the confirmed live-testing bug: department names typed in different
scripts/casing/whitespace (English "Sales" vs Arabic "مبيعات", "Finance" vs
"finance") were treated as separate groups instead of being merged, which
corrupted at-risk percentages and department-level cost/movement figures.

Uses the exact fixture case reported during live testing (Sales/مبيعات,
Finance/finance) against:
  1. backend/core/department_normalizer.py directly (the shared fix)
  2. backend/core/overtime_cost_intelligence_engine.py
  3. backend/core/payroll_movement_tracker.py (both operating modes)

Phase 40: employee_risk_scoring.py (the original "root department_summary
source" this file also covered) was removed along with its dedicated tests
here — see PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.

Run: py -m pytest tests/test_department_normalization_phase35_5.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.core.department_normalizer import (
    normalize_department_series,
    normalize_department_value,
)
from backend.core.overtime_cost_intelligence_engine import analyze_overtime_cost_intelligence
from backend.core.payroll_movement_tracker import analyze_payroll_movements

# The exact messy-data fixture values reported during live browser testing.
_MESSY_DEPARTMENTS = ["Sales", "مبيعات", "Finance", "finance", "Operations ", "Operations", "Sales", "Engineering"]


# ── 1. Direct unit tests on department_normalizer.py ───────────────────────

def test_sales_and_arabic_sales_merge_into_one_group():
    raw = pd.Series(["Sales", "مبيعات", "Sales"])
    result = normalize_department_series(raw)
    assert result.normalized_keys.nunique() == 1
    assert list(result.display_labels.values()) == ["Sales"]


def test_finance_casing_variants_merge_into_one_group():
    raw = pd.Series(["Finance", "finance", " Finance "])
    result = normalize_department_series(raw)
    assert result.normalized_keys.nunique() == 1
    assert list(result.display_labels.values()) == ["Finance"]


def test_messy_fixture_groups_into_four_correct_departments():
    """The exact 8-row fixture from live testing must collapse from 8 raw
    string values into 4 real departments: Sales(3), Finance(2), Operations(2), Engineering(1)."""
    result = normalize_department_series(pd.Series(_MESSY_DEPARTMENTS))
    counts = pd.Series(result.normalized_keys).value_counts()
    display_counts = {result.display_labels[k]: v for k, v in counts.items()}
    assert display_counts == {"Sales": 3, "Finance": 2, "Operations": 2, "Engineering": 1}


def test_curated_merges_are_disclosed_not_silent():
    result = normalize_department_series(pd.Series(["Sales", "مبيعات", "Finance", "finance"]))
    canonical_labels = {m.canonical_label for m in result.merges_applied}
    assert "Sales" in canonical_labels
    assert "Finance" in canonical_labels


def test_single_value_normalizer_handles_arabic_synonym():
    assert normalize_department_value("مبيعات") == "Sales"
    assert normalize_department_value("finance") == "Finance"
    assert normalize_department_value("  Sales  ") == "Sales"


def test_unrelated_unlisted_departments_are_not_merged():
    """Two genuinely different, unlisted department names must not be
    silently merged just because they happen to be similar-looking."""
    result = normalize_department_series(pd.Series(["Widgets North", "Widgets South"]))
    assert result.normalized_keys.nunique() == 2


# ── 1b. Regression: NaN/None/empty-string department values must not crash ──
# Confirmed live-testing regression: a fully-empty row, a row with
# Department="" (empty string), and a row with Department=None/NaN all
# crashed with `TypeError: 'float' object is not iterable`. Root cause:
# pandas 3.x's Series.astype(str) does NOT stringify NaN/None values (they
# survive as an actual float), so a raw NaN could leak into
# variants_by_key -> display_labels -> _is_latin_script(), which iterates
# over it expecting a string.

def test_nan_department_value_does_not_crash():
    raw = pd.Series(["Sales", np.nan, "Finance"])
    result = normalize_department_series(raw)  # must not raise
    assert all(isinstance(v, str) for v in result.display_labels.values())


def test_none_department_value_does_not_crash():
    raw = pd.Series(["Sales", None, "Finance"])
    result = normalize_department_series(raw)  # must not raise
    assert all(isinstance(v, str) for v in result.display_labels.values())


def test_empty_string_department_value_does_not_crash():
    raw = pd.Series(["Sales", "", "Finance"])
    result = normalize_department_series(raw)  # must not raise
    assert all(isinstance(v, str) for v in result.display_labels.values())


def test_astype_str_does_not_stringify_nan_on_this_pandas_version():
    """Documents the actual root cause: astype(str) leaves NaN as a float
    on this pandas version, so callers must never rely on it alone."""
    raw = pd.Series(["Sales", np.nan]).astype(str)
    assert isinstance(raw.iloc[1], float)  # NOT the string "nan"


def test_missing_department_values_route_to_unknown_bucket():
    raw = pd.Series(["Sales", np.nan, None, "", "Sales"])
    result = normalize_department_series(raw)
    labels = {result.display_labels[k] for k in result.normalized_keys}
    assert "Unknown / Unspecified Department" in labels
    counts = pd.Series(result.normalized_keys).map(result.display_labels).value_counts()
    assert counts["Unknown / Unspecified Department"] == 3
    assert counts["Sales"] == 2


def test_mixed_valid_and_missing_departments_end_to_end_no_crash():
    """Reproduces the exact live-testing fixture shape: a fully-empty row,
    an empty-string department, and a None/NaN department mixed with real
    messy Sales/مبيعات/Finance/finance values, run through the surviving
    consuming modules end-to-end. Phase 40: employee_risk_scoring.py (the
    third original consumer) was removed — its coverage here was removed
    with it."""
    from backend.core.overtime_cost_intelligence_engine import analyze_overtime_cost_intelligence
    from backend.core.payroll_movement_tracker import analyze_payroll_movements

    df = pd.DataFrame({
        "EmployeeID": ["EMP001", "EMP002", "EMP003", "EMP004", "EMP005", "EMP006", "EMP007", None],
        "Department": ["Sales", "مبيعات", "Finance", "finance", None, "", "Operations", np.nan],
        "OverTime": ["Yes", "No", "Yes", "No", "Yes", "No", "Yes", np.nan],
        "MonthlyIncome": [10000, 11000, 12000, 13000, 9000, 9500, 10500, np.nan],
        "PercentSalaryHike": [5.0, 6.0, 3.0, 4.0, 2.0, 2.5, 5.5, np.nan],
    })
    df.loc[7] = [np.nan] * len(df.columns)  # fully-empty row

    overtime_result = analyze_overtime_cost_intelligence(df)  # must not raise
    assert overtime_result.available is True

    payroll_result = analyze_payroll_movements(df)  # must not raise
    assert payroll_result.data_mode in ("cross_sectional_snapshot", "unavailable")


# ── 2. overtime_cost_intelligence_engine.py ─────────────────────────────────

def _messy_overtime_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Department": _MESSY_DEPARTMENTS,
        "OverTime": ["Yes", "No", "Yes", "No", "Yes", "No", "Yes", "No"],
        "MonthlyIncome": [10000, 10500, 11000, 11500, 9000, 9500, 10200, 12000],
    })


def test_overtime_engine_merges_messy_departments():
    result = analyze_overtime_cost_intelligence(_messy_overtime_df())
    assert result.available is True
    dept_counts = {d.department: d.n_employees for d in result.department_breakdown}
    assert dept_counts == {"Sales": 3, "Finance": 2, "Operations": 2, "Engineering": 1}


def test_overtime_engine_discloses_department_merges():
    result = analyze_overtime_cost_intelligence(_messy_overtime_df())
    notes_text = " ".join(result.department_normalization_notes)
    assert "Sales" in notes_text
    assert "Finance" in notes_text


# ── 4. payroll_movement_tracker.py — snapshot-proxy mode ────────────────────

def _messy_snapshot_df() -> pd.DataFrame:
    return pd.DataFrame({
        "EmployeeID": [f"E{i}" for i in range(len(_MESSY_DEPARTMENTS))],
        "Department": _MESSY_DEPARTMENTS,
        "PercentSalaryHike": [5.0, 6.0, 3.0, 4.0, 2.0, 2.5, 5.5, 1.0],
    })


def test_payroll_snapshot_proxy_merges_messy_departments():
    result = analyze_payroll_movements(_messy_snapshot_df())
    assert result.data_mode == "cross_sectional_snapshot"
    dept_counts = {d.department: d.n_employees for d in result.department_breakdown}
    assert dept_counts == {"Sales": 3, "Finance": 2, "Operations": 2, "Engineering": 1}
    notes_text = " ".join(result.department_normalization_notes)
    assert "Sales" in notes_text
    assert "Finance" in notes_text


# ── 4b. payroll_movement_tracker.py — longitudinal mode ──────────────────────

def _messy_longitudinal_df() -> pd.DataFrame:
    depts = {
        "E1": ["Sales", "Sales"], "E2": ["مبيعات", "مبيعات"], "E3": ["Sales", "Sales"],
        "E4": ["Finance", "Finance"], "E5": ["finance", "finance"],
        "E6": ["Operations ", "Operations"], "E7": ["Operations", "Operations"],
    }
    rows = []
    for emp, dvals in depts.items():
        for i, period in enumerate([2023, 2024]):
            rows.append({"EmployeeID": emp, "Period": period, "Salary": 10000 + i * 500, "Department": dvals[i]})
    return pd.DataFrame(rows)


def test_payroll_longitudinal_merges_messy_departments():
    result = analyze_payroll_movements(_messy_longitudinal_df())
    assert result.data_mode == "longitudinal"
    dept_counts = {d.department: d.n_employees for d in result.department_breakdown}
    assert dept_counts == {"Sales": 3, "Finance": 2, "Operations": 2}
    notes_text = " ".join(result.department_normalization_notes)
    assert "Sales" in notes_text
    assert "Finance" in notes_text
