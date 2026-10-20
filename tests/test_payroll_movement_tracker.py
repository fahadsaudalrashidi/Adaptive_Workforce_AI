"""
Phase 35.2 — Payroll Movements Tracker tests.

Covers all three operating modes: unavailable (no salary-movement column),
cross-sectional snapshot proxy (PercentSalaryHike-style), and longitudinal
(genuine multi-period history). Uses the real in-repo test_employee_data.csv
fixture for the "unavailable" path (it genuinely has neither column type),
and synthetic in-memory DataFrames for the other two modes — standard,
appropriate unit-test practice (not the "fabricating output data shown to a
user" this module's docstring warns against; these are test inputs, not
values the platform presents as real).

Run: py -m pytest tests/test_payroll_movement_tracker.py -v
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.core.payroll_movement_tracker import (
    analyze_payroll_movements,
    payroll_movement_to_dict,
    unavailable_payroll_result,
)

_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "test_employee_data.csv"


# ── Mode 3: unavailable ──────────────────────────────────────────────────────

def test_unavailable_on_real_fixture_with_no_movement_columns():
    """test_employee_data.csv genuinely has no hike or period column."""
    df = pd.read_csv(_FIXTURE_PATH)
    result = analyze_payroll_movements(df)
    assert result.available is False
    assert result.data_mode == "unavailable"
    assert result.department_breakdown == []
    assert "period" in result.limitation_note_en.lower() or "snapshot" in result.limitation_note_en.lower()


def test_unavailable_on_empty_dataframe():
    result = analyze_payroll_movements(pd.DataFrame())
    assert result.available is False


def test_unavailable_result_has_no_fabricated_numbers():
    result = unavailable_payroll_result("test reason")
    assert result.org_avg_hike_pct is None
    assert result.n_periods_detected is None
    assert result.department_breakdown == []


# ── Mode 2: cross-sectional snapshot proxy ──────────────────────────────────

@pytest.fixture
def snapshot_df():
    rng = np.random.default_rng(7)
    n = 90
    return pd.DataFrame({
        "Department": rng.choice(["Sales", "Engineering", "HR"], n),
        "PercentSalaryHike": rng.uniform(10, 25, n).round(1),
    })


def test_snapshot_proxy_detected_and_labeled(snapshot_df):
    result = analyze_payroll_movements(snapshot_df)
    assert result.available is True
    assert result.data_mode == "cross_sectional_snapshot"
    assert result.n_periods_detected == 1
    # Must be explicit that this is NOT a tracked history.
    assert "not a tracked history" in result.comparison_note_en


def test_snapshot_proxy_org_avg_matches_real_mean(snapshot_df):
    result = analyze_payroll_movements(snapshot_df)
    expected = round(float(snapshot_df["PercentSalaryHike"].mean()), 2)
    assert result.org_avg_hike_pct == pytest.approx(expected)


def test_snapshot_proxy_department_breakdown_matches_groupby(snapshot_df):
    """"HR" is a curated synonym for "Human Resources" (department_normalizer.py),
    so it is canonicalized in the display label even though it's the only raw
    variant present — group the expected values the same way the fixture's
    raw "HR" is expected to now display."""
    result = analyze_payroll_movements(snapshot_df)
    expected_by_dept = snapshot_df.groupby("Department")["PercentSalaryHike"].mean().round(2)
    got_by_dept = {d.department: d.avg_hike_pct for d in result.department_breakdown}
    label_map = {"Sales": "Sales", "Engineering": "Engineering", "HR": "Human Resources"}
    for dept, expected_val in expected_by_dept.items():
        assert got_by_dept[label_map[dept]] == pytest.approx(float(expected_val))


def test_snapshot_proxy_with_risk_scores_produces_group_comparison(snapshot_df):
    rng = np.random.default_rng(11)
    risk_scores = pd.Series(rng.uniform(20, 80, len(snapshot_df)))
    result = analyze_payroll_movements(snapshot_df, employee_risk_scores=risk_scores)
    assert "above-median" in result.comparison_note_en
    assert "does not establish that salary movement causes" in result.comparison_note_en


def test_snapshot_proxy_without_risk_scores_has_no_group_comparison_claim(snapshot_df):
    result = analyze_payroll_movements(snapshot_df, employee_risk_scores=None)
    assert "above-median" not in result.comparison_note_en


def test_limitation_note_explains_how_to_unlock_longitudinal(snapshot_df):
    result = analyze_payroll_movements(snapshot_df)
    assert "period" in result.limitation_note_en.lower()
    assert "employee-id" in result.limitation_note_en.lower() or "employee-ID" in result.limitation_note_en


# ── Mode 1: longitudinal ─────────────────────────────────────────────────────

@pytest.fixture
def longitudinal_df():
    rng = np.random.default_rng(3)
    rows = []
    for emp in range(1, 31):
        base_salary = rng.uniform(8000, 16000)
        dept = "Sales" if emp % 3 == 0 else ("Engineering" if emp % 3 == 1 else "HR")
        for period in range(1, 5):
            rows.append({
                "EmployeeID": f"E{emp:03d}",
                "Period": period,
                "MonthlyIncome": round(base_salary * (1 + 0.015 * period), 2),
                "Department": dept,
            })
    return pd.DataFrame(rows)


def test_longitudinal_data_mode_detected(longitudinal_df):
    result = analyze_payroll_movements(longitudinal_df)
    assert result.available is True
    assert result.data_mode == "longitudinal"
    assert result.n_periods_detected == 4
    assert result.n_employees_total == 30


def test_longitudinal_avg_hike_is_positive_for_growing_salaries(longitudinal_df):
    """Every employee's salary grows every period in the fixture — average
    period-over-period change must be positive and close to the ~1.5% step."""
    result = analyze_payroll_movements(longitudinal_df)
    assert result.org_avg_hike_pct > 0
    assert result.org_avg_hike_pct == pytest.approx(1.5, abs=0.3)


def test_longitudinal_flat_salaries_yield_zero_movement():
    rows = []
    for emp in range(1, 11):
        for period in range(1, 4):
            rows.append({"EmployeeID": f"E{emp}", "Period": period, "MonthlyIncome": 10000.0})
    df = pd.DataFrame(rows)
    result = analyze_payroll_movements(df)
    assert result.available is True
    assert result.data_mode == "longitudinal"
    assert result.org_avg_hike_pct == pytest.approx(0.0)


def test_longitudinal_requires_minimum_multi_period_employees():
    """Only 2 employees have repeat records — below the 5-employee floor,
    should NOT be treated as longitudinal (falls through to unavailable)."""
    rows = [
        {"EmployeeID": "E1", "Period": 1, "MonthlyIncome": 10000},
        {"EmployeeID": "E1", "Period": 2, "MonthlyIncome": 10500},
        {"EmployeeID": "E2", "Period": 1, "MonthlyIncome": 9000},
        {"EmployeeID": "E2", "Period": 2, "MonthlyIncome": 9200},
    ] + [{"EmployeeID": f"E{i}", "Period": 1, "MonthlyIncome": 8000} for i in range(3, 8)]
    df = pd.DataFrame(rows)
    result = analyze_payroll_movements(df)
    assert result.data_mode == "unavailable"


def test_longitudinal_department_breakdown_sums_employees(longitudinal_df):
    result = analyze_payroll_movements(longitudinal_df)
    total_from_depts = sum(d.n_employees for d in result.department_breakdown)
    assert total_from_depts == result.n_employees_total


# ── Serialization ────────────────────────────────────────────────────────────

def test_to_dict_is_json_safe(longitudinal_df):
    result = analyze_payroll_movements(longitudinal_df)
    d = payroll_movement_to_dict(result)
    assert d["available"] is True
    assert d["data_mode"] == "longitudinal"
    assert isinstance(d["department_breakdown"], list)
