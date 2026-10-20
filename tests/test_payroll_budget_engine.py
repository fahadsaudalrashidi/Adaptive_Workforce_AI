"""
Phase 37 — Payroll Budget (Planned vs. Actual) tests.

Hand-computed variance figures against a real fixture. Central disciplines
under test: actual totals are the REAL sum of only clean numeric salaries
(never avg*headcount, which would silently impute the average onto
employees with an unknown salary); departments with actual data but no
submitted plan are flagged, never assumed a zero budget; departments with
a planned entry but no actual employees are flagged, never silently
dropped; department_normalizer.py is genuinely reused (IT/HR abbreviations
expand to canonical labels).

Run: py -m pytest tests/test_payroll_budget_engine.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.payroll_budget_engine import (
    PlannedDepartmentBudget,
    compute_payroll_budget_variance,
    payroll_budget_result_to_dict,
    unavailable_payroll_budget_result,
)

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _ROOT / "payroll_budget_test_data.csv"


def _load() -> pd.DataFrame:
    return pd.read_csv(_FIXTURE)


_PLANNED = {
    "Finance": PlannedDepartmentBudget(planned_headcount=2, planned_avg_salary_sar=10000.0),
    "Information Technology": PlannedDepartmentBudget(planned_headcount=3, planned_avg_salary_sar=15000.0),
    "Marketing": PlannedDepartmentBudget(planned_headcount=5, planned_avg_salary_sar=7000.0),
}


class TestBasicAvailability:
    def test_available_with_real_fixture(self):
        r = compute_payroll_budget_variance(_load(), {})
        assert r.available is True
        assert r.n_employees_total == 7

    def test_missing_department_column_unavailable(self):
        df = _load().drop(columns=["Department"])
        r = compute_payroll_budget_variance(df, {})
        assert r.available is False
        assert r.columns_detected["department"] is False

    def test_empty_dataframe_unavailable(self):
        r = compute_payroll_budget_variance(pd.DataFrame(), {})
        assert r.available is False

    def test_unavailable_helper_never_raises(self):
        r = unavailable_payroll_budget_result("no data")
        assert r.available is False
        assert r.department_variances == []


class TestActualAggregation:
    def test_actual_totals_are_real_sum_not_imputed(self):
        """IT has 3 employees but one has a range-text salary — actual_total
        must be exactly 15000+17000=32000, NEVER avg(16000)*3=48000."""
        r = compute_payroll_budget_variance(_load(), {})
        it = next(d for d in r.department_variances if d.department == "Information Technology")
        assert it.actual_headcount == 3
        assert it.actual_avg_salary_sar == pytest.approx(16000.0)
        assert it.actual_total_payroll_sar == pytest.approx(32000.0)
        assert it.n_excluded_invalid_salary == 1

    def test_finance_actual_totals(self):
        r = compute_payroll_budget_variance(_load(), {})
        fin = next(d for d in r.department_variances if d.department == "Finance")
        assert fin.actual_headcount == 2
        assert fin.actual_total_payroll_sar == pytest.approx(22000.0)

    def test_department_normalizer_reused(self):
        r = compute_payroll_budget_variance(_load(), {})
        depts = {d.department for d in r.department_variances}
        assert depts == {"Finance", "Information Technology", "Sales", "Human Resources"}

    def test_company_actual_totals(self):
        r = compute_payroll_budget_variance(_load(), {})
        assert r.company_actual_headcount == 7
        assert r.company_actual_total_payroll_sar == pytest.approx(71000.0)


class TestVarianceWithPlan:
    def test_finance_variance_hand_computed(self):
        r = compute_payroll_budget_variance(_load(), _PLANNED)
        fin = next(d for d in r.department_variances if d.department == "Finance")
        assert fin.planned_total_payroll_sar == pytest.approx(20000.0)
        assert fin.headcount_variance == 0
        assert fin.payroll_cost_variance_sar == pytest.approx(2000.0)
        assert fin.payroll_cost_variance_pct == pytest.approx(10.0)

    def test_it_variance_hand_computed(self):
        r = compute_payroll_budget_variance(_load(), _PLANNED)
        it = next(d for d in r.department_variances if d.department == "Information Technology")
        assert it.planned_total_payroll_sar == pytest.approx(45000.0)
        assert it.payroll_cost_variance_sar == pytest.approx(32000.0 - 45000.0)
        assert it.payroll_cost_variance_pct == pytest.approx(-28.9, abs=0.1)

    def test_department_with_actual_but_no_plan_flagged(self):
        r = compute_payroll_budget_variance(_load(), _PLANNED)
        assert "Sales" in r.departments_missing_planned_budget
        assert "Human Resources" in r.departments_missing_planned_budget
        sales = next(d for d in r.department_variances if d.department == "Sales")
        assert sales.planned_submitted is False
        assert sales.payroll_cost_variance_sar is None  # never fabricated as 0

    def test_department_with_plan_but_no_actual_flagged(self):
        r = compute_payroll_budget_variance(_load(), _PLANNED)
        assert "Marketing" in r.planned_departments_missing_actual_data
        marketing = next(d for d in r.department_variances if d.department == "Marketing")
        assert marketing.actual_present is False
        assert marketing.actual_headcount == 0
        assert marketing.actual_total_payroll_sar is None
        assert marketing.headcount_variance is None  # never fabricated

    def test_company_wide_variance_hand_computed(self):
        r = compute_payroll_budget_variance(_load(), _PLANNED)
        # actual: 71000 total, 7 headcount. planned: Finance 20000+2, IT 45000+3, Marketing 35000+5
        assert r.company_planned_headcount == 10
        assert r.company_planned_total_payroll_sar == pytest.approx(100000.0)
        assert r.company_headcount_variance == -3
        assert r.company_headcount_variance_pct == pytest.approx(-30.0)
        assert r.company_payroll_cost_variance_sar == pytest.approx(71000.0 - 100000.0)
        assert r.company_payroll_cost_variance_pct == pytest.approx(-29.0)

    def test_no_plan_submitted_company_variance_is_none(self):
        r = compute_payroll_budget_variance(_load(), {})
        assert r.company_planned_headcount is None
        assert r.company_headcount_variance is None
        assert r.company_payroll_cost_variance_sar is None


class TestSerialization:
    def test_to_dict_serializes(self):
        r = compute_payroll_budget_variance(_load(), _PLANNED)
        d = payroll_budget_result_to_dict(r)
        assert d["available"] is True
        assert len(d["department_variances"]) == 5  # Finance, IT, Sales, HR, Marketing (union of actual + planned)
        assert d["company_payroll_cost_variance_sar"] == pytest.approx(-29000.0)
