"""
Phase 35.1 — Overtime & Workforce Cost Intelligence Engine tests.

Uses the real, previously-orphaned in-repo fixture test_employee_data.csv
(200 rows, real OverTime Yes/No + MonthlyIncome columns) so these are
genuine computed-value assertions against real data, not mocks.

Run: py -m pytest tests/test_overtime_cost_intelligence_engine.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.overtime_cost_intelligence_engine import (
    ASSUMED_MONTHLY_OVERTIME_HOURS_FOR_FLAGGED_EMPLOYEE,
    OVERTIME_PREMIUM_MULTIPLIER,
    STANDARD_MONTHLY_HOURS,
    analyze_overtime_cost_intelligence,
    overtime_cost_intelligence_to_dict,
    unavailable_overtime_result,
)

_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "test_employee_data.csv"


@pytest.fixture(scope="module")
def real_employee_df() -> pd.DataFrame:
    assert _FIXTURE_PATH.exists(), f"expected fixture at {_FIXTURE_PATH}"
    return pd.read_csv(_FIXTURE_PATH)


@pytest.fixture
def sample_department_summary():
    return [
        {"group_value": "Sales", "average_risk_score": 62.0},
        {"group_value": "Operations", "average_risk_score": 40.0},
        {"group_value": "HR", "average_risk_score": 35.0},
        {"group_value": "Finance", "average_risk_score": 58.0},
        {"group_value": "Engineering", "average_risk_score": 45.0},
    ]


# ── Column detection ─────────────────────────────────────────────────────────

def test_detects_overtime_flag_and_real_salary_column(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df)
    assert result.available is True
    assert result.hours_source == "assumed"     # OverTime is Yes/No, not an hours count
    assert result.wage_source == "observed"     # MonthlyIncome is a real numeric column


def test_unavailable_when_no_overtime_column_present():
    df = pd.DataFrame({
        "Department": ["Sales", "Engineering"],
        "MonthlyIncome": [10000, 12000],
    })
    result = analyze_overtime_cost_intelligence(df)
    assert result.available is False
    assert "overtime" in (result.reason or "").lower()
    assert result.org_monthly_overtime_cost_sar == 0.0


def test_unavailable_on_empty_dataframe():
    result = analyze_overtime_cost_intelligence(pd.DataFrame())
    assert result.available is False


# ── Real computed-value assertions ──────────────────────────────────────────

def test_overtime_prevalence_matches_real_flag_count(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df)
    expected_flagged = int((real_employee_df["OverTime"].astype(str).str.strip().str.lower() == "yes").sum())
    assert result.n_overtime_employees == expected_flagged
    assert result.n_employees_total == len(real_employee_df)
    assert result.overtime_prevalence_pct == pytest.approx(
        100.0 * expected_flagged / len(real_employee_df), abs=0.1
    )


def test_org_monthly_cost_matches_manual_calculation(real_employee_df):
    """
    Independently recompute the expected org-wide monthly overtime cost from
    the raw dataframe using the same documented formula (hours x hourly_wage
    x 1.5 premium) and assert the module's output matches exactly.
    """
    result = analyze_overtime_cost_intelligence(real_employee_df)

    flagged = real_employee_df["OverTime"].astype(str).str.strip().str.lower() == "yes"
    hours = flagged.astype(float) * ASSUMED_MONTHLY_OVERTIME_HOURS_FOR_FLAGGED_EMPLOYEE
    hourly_wage = real_employee_df["MonthlyIncome"].astype(float) / STANDARD_MONTHLY_HOURS
    expected_monthly_cost = round(float((hours * hourly_wage * OVERTIME_PREMIUM_MULTIPLIER).sum()), 0)

    assert result.org_monthly_overtime_cost_sar == pytest.approx(expected_monthly_cost)
    assert result.org_annual_overtime_cost_sar == pytest.approx(expected_monthly_cost * 12)


def test_department_breakdown_sums_to_org_total(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df)
    dept_sum = sum(d.monthly_overtime_cost_sar for d in result.department_breakdown)
    assert dept_sum == pytest.approx(result.org_monthly_overtime_cost_sar, rel=1e-6)


def test_department_breakdown_covers_all_employees(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df)
    total_from_depts = sum(d.n_employees for d in result.department_breakdown)
    assert total_from_depts == result.n_employees_total


def test_zero_overtime_employees_yields_zero_cost():
    df = pd.DataFrame({
        "Department": ["A", "B", "C"],
        "MonthlyIncome": [10000, 12000, 9000],
        "OverTime": ["No", "No", "No"],
    })
    result = analyze_overtime_cost_intelligence(df)
    assert result.available is True
    assert result.n_overtime_employees == 0
    assert result.org_monthly_overtime_cost_sar == 0.0
    assert result.overtime_prevalence_pct == 0.0


# ── Risk cross-reference (non-causal) ───────────────────────────────────────

def test_department_with_high_overtime_and_high_risk_is_flagged(real_employee_df, sample_department_summary):
    """
    Sales (40% overtime prevalence per the fixture, average_risk_score=62)
    must be flagged elevated; Engineering (also 40% overtime, but
    average_risk_score=45, below the 55 threshold) must not be.
    """
    result = analyze_overtime_cost_intelligence(
        real_employee_df, sample_department_summary, risk_elevated_threshold=55.0,
    )
    dept_by_name = {d.department: d for d in result.department_breakdown}
    assert dept_by_name["Sales"].elevated_overtime_and_risk is True
    assert dept_by_name["Engineering"].elevated_overtime_and_risk is False
    assert "Sales" in result.elevated_risk_departments
    assert "Engineering" not in result.elevated_risk_departments


def test_no_department_summary_leaves_risk_score_none(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df, department_summary=None)
    for d in result.department_breakdown:
        assert d.average_risk_score is None
        assert d.elevated_overtime_and_risk is False
    assert result.elevated_risk_departments == []


def test_narrative_uses_non_causal_language(real_employee_df, sample_department_summary):
    """
    Governance requirement: never AFFIRMATIVELY claim overtime causes
    elevated risk. Explicitly negated causal language ("not evidence that
    X causes Y") is the required safe pattern and must remain present.
    """
    result = analyze_overtime_cost_intelligence(real_employee_df, sample_department_summary)
    lowered = result.narrative_en.lower()
    assert "will cause" not in lowered
    assert "guaranteed" not in lowered
    assert "certain to" not in lowered
    # Must explicitly disclaim causality when a co-occurrence is reported —
    # the word "causes" is only acceptable inside this negation.
    if result.elevated_risk_departments:
        assert "not evidence that overtime causes" in result.narrative_en
        # No affirmative (non-negated) causal claim should exist elsewhere.
        assert lowered.count("causes") == 1


def test_assumed_hours_disclaimer_present_when_no_hours_column(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df)
    assert result.hours_source == "assumed"
    assert "engineering assumption" in result.governance_note.lower()


def test_sources_cite_saudi_labour_law(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df)
    assert any("Article 107" in s for s in result.sources)
    assert any("Article 98" in s for s in result.sources)


# ── Serialization ────────────────────────────────────────────────────────────

def test_to_dict_is_json_safe_and_complete(real_employee_df, sample_department_summary):
    result = analyze_overtime_cost_intelligence(real_employee_df, sample_department_summary)
    d = overtime_cost_intelligence_to_dict(result)
    assert d["available"] is True
    assert isinstance(d["department_breakdown"], list) and len(d["department_breakdown"]) == 5
    assert isinstance(d["elevated_risk_departments"], list)
    assert isinstance(d["sources"], list) and len(d["sources"]) >= 2


def test_unavailable_result_serializes_cleanly():
    result = unavailable_overtime_result("test reason")
    d = overtime_cost_intelligence_to_dict(result)
    assert d["available"] is False
    assert d["reason"] == "test reason"
    assert d["department_breakdown"] == []


# ── Phase 35.5 correction: Phase 4 sector benchmarking wired into this page ──
# (financial_intelligence_engine.py's GASTAT-cited employment-sector salary
# model was previously computed only inside report exporters, never on any
# live page. This is the only live page that already consumes
# financial_intelligence_engine.py's salary estimator, so the honest
# confidence label is surfaced here rather than adding a new page.)

def test_salary_benchmark_confidence_observed_when_real_salary_column_present(real_employee_df):
    result = analyze_overtime_cost_intelligence(real_employee_df)
    assert result.wage_source == "observed"
    assert result.salary_benchmark_confidence == "observed"


def test_salary_benchmark_confidence_uncalibrated_when_no_signal():
    df = pd.DataFrame({
        "Department": ["Sales", "Engineering"],
        "OverTime": ["Yes", "No"],
    })
    result = analyze_overtime_cost_intelligence(df)
    assert result.wage_source == "estimated"
    assert result.salary_benchmark_confidence == "uncalibrated_generic_estimate"
    assert result.employment_sector_used is None


def test_salary_benchmark_confidence_gastat_when_employment_sector_inferred():
    """No real salary column, but department metadata implies a government
    employer — must use the real, GASTAT-cited employment-sector table."""
    df = pd.DataFrame({
        "Department": ["Ministry of Finance", "Ministry of Finance"],
        "OverTime": ["Yes", "No"],
    })
    department_summary = [{"group_value": "Ministry of Finance", "average_risk_score": 50.0}]
    result = analyze_overtime_cost_intelligence(df, department_summary)
    assert result.wage_source == "estimated"
    assert result.salary_benchmark_confidence == "gastat_official_2018"
    assert result.employment_sector_used == "public"


def test_salary_benchmark_confidence_and_sector_are_serialized():
    result = analyze_overtime_cost_intelligence(
        pd.DataFrame({"Department": ["Sales"], "OverTime": ["Yes"]}),
    )
    d = overtime_cost_intelligence_to_dict(result)
    assert "salary_benchmark_confidence" in d
    assert "employment_sector_used" in d
