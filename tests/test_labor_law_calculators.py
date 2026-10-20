"""
Phase 21 — Saudi Labor Law Calculators (End-of-Service Gratuity, WPS/Payroll
Consistency, Leave Balance & Compensation) tests.

These compute REAL legal payment amounts, not illustrative estimates — the
central discipline under test throughout this file is that NONE of the
three calculators ever substitutes a range-text midpoint (or any other
estimate) for a real numeric salary/years-of-service value. Every test in
the "honest degradation" sections below asserts `available is False` (or,
for Part 2, `check_applicable is False`) rather than a fabricated figure.

Covers, each with real computed-value assertions:
  1. Gratuity: hand-computed values across every Article 85 resignation
     tier (<2y=0, 2-5y=1/3, 5-10y=2/3, 10y+=full), employer-termination
     (always full award), unspecified separation (both scenarios shown),
     and the year-5 boundary in the base Article 84 formula itself
     (fractional years spanning both the 0.5x and 1.0x bands).
  2. Gratuity strict-salary refusal: a synthetic fixture with range-text
     salary values (the same shape Phase 20 found in the real Original
     Dataset of Employee Attrition) must be excluded, never midpointed.
  3. Leave: hand-computed cumulative entitlement across the 5-year 21-vs-30
     day boundary, compensation-for-unused-leave using the Article 111
     daily-wage-over-30 formula, and the entitlement-only fallback when no
     leave-balance/leave-taken column exists.
  4. WPS consistency: real mismatches detected and correctly quantified
     against a synthetic two-column fixture, a three-way
     base+allowances=total check, and the "not applicable" honest state
     against a real single-salary-column fixture already in this repo.
  5. Department rollup (department_normalizer.py reuse) and PII safety
     (record_id_safe hashing — no raw employee ID ever appears in output).

Run: py -m pytest tests/test_labor_law_calculators.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.labor_law_calculators import (
    ANNUAL_LEAVE_DAYS_5YR_PLUS,
    ANNUAL_LEAVE_DAYS_UNDER_5YR,
    LEAVE_COMPENSATION_DAY_DIVISOR,
    _AS_OF_DATE_PATTERNS,
    _HIRE_DATE_PATTERNS,
    _LAST_WORKING_DAY_PATTERNS,
    _LEAVE_BALANCE_PATTERNS,
    _LEAVE_TAKEN_PATTERNS,
    analyze_gratuity,
    analyze_leave_balance,
    analyze_wps_consistency,
    gratuity_to_dict,
    leave_balance_to_dict,
    unavailable_gratuity_result,
    unavailable_leave_result,
    unavailable_wps_result,
    wps_consistency_to_dict,
)

_ROOT = Path(__file__).resolve().parent.parent
_CLEAN_FIXTURE = _ROOT / "labor_law_clean_data_test.csv"
_WPS_FIXTURE = _ROOT / "labor_law_wps_test_data.csv"
_REAL_SINGLE_SALARY_FIXTURE = _ROOT / "test_employee_data.csv"
_LEAVE_BALANCE_DAYS_FIXTURE = _ROOT / "labor_law_leave_balance_days_test_data.csv"


# ── 1. Gratuity: hand-computed across every Article 85 tier ────────────────

def test_gratuity_resignation_under_2_years_is_zero():
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 1.0)
    assert c.separation_type == "resignation"
    assert c.gratuity_full_award_sar == 5000.0   # 10000 * 1 * 0.5
    assert c.gratuity_if_resignation_sar == 0.0  # Article 85: <2 years = none
    assert c.applicable_amount_sar == 0.0
    assert c.applicable_scenario == "resignation"


def test_gratuity_resignation_2_to_5_years_is_one_third():
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 3.0)
    assert c.gratuity_full_award_sar == 15000.0        # 10000 * 3 * 0.5
    assert c.gratuity_if_resignation_sar == 5000.0      # 15000 / 3
    assert c.applicable_amount_sar == 5000.0


def test_gratuity_resignation_5_to_10_years_is_two_thirds():
    """Also exercises the Article 84 year-5 boundary in the base formula:
    7 years = 5 years at 0.5x + 2 years at 1.0x = 25000 + 20000 = 45000."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 7.0)
    assert c.gratuity_full_award_sar == 45000.0
    assert c.gratuity_if_resignation_sar == pytest.approx(30000.0, abs=0.01)  # 45000 * 2/3
    assert c.applicable_amount_sar == pytest.approx(30000.0, abs=0.01)


def test_gratuity_resignation_10_plus_years_is_full():
    """12 years = 5 * 0.5 + 7 * 1.0 = 25000 + 70000 = 95000; resignation
    fraction at 10+ years is 1.0 (full), matching the full award exactly."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 12.0)
    assert c.gratuity_full_award_sar == 95000.0
    assert c.gratuity_if_resignation_sar == 95000.0
    assert c.applicable_amount_sar == 95000.0
    assert c.applicable_scenario == "resignation"


def test_gratuity_lowercase_resignation_token_classified_correctly():
    """E4's raw value is 'resigned' (lowercase, different word form) — must
    still classify as resignation, not fall through as unspecified."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 12.0)
    assert c.separation_type == "resignation"


def test_gratuity_termination_always_full_award_regardless_of_tenure():
    """6 years, employer termination: full award = 8000*5*0.5 + 8000*1*1.0
    = 20000 + 8000 = 28000 — Article 85's resignation reduction does NOT
    apply to employer termination."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 6.0)
    assert c.separation_type == "employer_termination_or_end_of_contract"
    assert c.gratuity_full_award_sar == 28000.0
    assert c.applicable_amount_sar == 28000.0
    assert c.applicable_scenario == "full_termination"


def test_gratuity_end_of_contract_phrase_classified_as_termination():
    """5.5 years spans the year-5 boundary within a single fractional
    value: 5*0.5 + 0.5*1.0 = 2.5 + 0.5 = 3.0 months -> *9000 = 27000."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 5.5)
    assert c.separation_type == "employer_termination_or_end_of_contract"
    assert c.gratuity_full_award_sar == 27000.0
    assert c.applicable_scenario == "full_termination"


def test_gratuity_unspecified_separation_shows_both_scenarios():
    """4 years, no separation type: full=24000, resignation-if-applicable
    =8000 (1/3) — BOTH must be present and distinct, applicable defaults
    to the full award with an explicit 'unspecified_both_shown' label
    rather than silently picking one."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    c = next(c for c in result.candidates if c.years_of_service == 4.0)
    assert c.separation_type is None
    assert c.gratuity_full_award_sar == 24000.0
    assert c.gratuity_if_resignation_sar == pytest.approx(8000.0, abs=0.01)
    assert c.applicable_scenario == "unspecified_both_shown"


def test_gratuity_department_rollup_reuses_department_normalizer():
    """'HR' normalizes to the canonical 'Human Resources' via
    department_normalizer.py's own curated synonym table — proof this is
    real reuse, not a bypassed/reimplemented normalizer."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    depts = {d.department for d in result.department_breakdown}
    assert {"Sales", "Engineering", "Finance", "Human Resources"}.issubset(depts)
    engineering = next(d for d in result.department_breakdown if d.department == "Engineering")
    assert engineering.n_employees == 2  # years=7 and years=12 rows
    assert engineering.total_full_award_sar == pytest.approx(45000.0 + 95000.0, abs=0.01)


# ── 2. Gratuity strict-salary refusal (the central Phase 21 discipline) ────

def test_gratuity_range_text_salary_never_produces_a_figure():
    """Same shape of range-text Phase 20 found in the real Original Dataset
    of Employee Attrition ('From X to Y SAR'). No employee here has a clean
    numeric salary — the whole result must be unavailable, never a
    midpoint-based legal figure."""
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3"],
        "Department": ["Sales", "Sales", "Engineering"],
        "YearsAtCompany": [3, 7, 12],
        "MonthlySalary": ["From 5000 to 10000 SAR", "Less than 5000 SAR", "More than 15000 SAR"],
    })
    result = analyze_gratuity(df)
    assert result.available is False
    assert result.candidates == []
    assert "range-text" in result.reason.lower() or "clean" in result.reason.lower()
    assert "5000" in result.reason  # the example bad value is surfaced


def test_gratuity_partial_range_text_excludes_only_bad_rows():
    """A MIXED dataset (some rows clean, some range-text) must compute real
    figures for the clean rows and exclude+count the bad ones — not refuse
    the whole dataset just because some rows are messy."""
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3"],
        "Department": ["Sales", "Sales", "Sales"],
        "YearsAtCompany": [3, 3, 3],
        "MonthlySalary": [9000, "From 5000 to 10000 SAR", 9000],
    })
    result = analyze_gratuity(df)
    assert result.available is True
    assert result.n_valid_computed == 2
    assert result.n_excluded_invalid_salary == 1
    assert all(c.monthly_wage_sar == 9000.0 for c in result.candidates)


def test_gratuity_no_salary_or_years_column_is_unavailable():
    df = pd.DataFrame({"EmployeeID": ["E1"], "Department": ["Sales"]})
    result = analyze_gratuity(df)
    assert result.available is False
    assert result.columns_detected["salary"] is False
    assert result.columns_detected["years_of_service"] is False


def test_unavailable_gratuity_result_never_fabricates():
    result = unavailable_gratuity_result("No salary column detected.", {"salary": False})
    assert result.available is False
    assert result.candidates == []
    assert result.department_breakdown == []
    d = gratuity_to_dict(result)
    assert d["candidates"] == []


# ── 3. Leave: entitlement, compensation, entitlement-only fallback ─────────

def test_leave_entitlement_boundary_at_five_years():
    """Independently verifies the constants match the module's own
    computation: 5 years exactly = 5*21=105 (still in the 21-day band);
    7 years = 5*21 + 2*30 = 105+60=165 (crossed into the 30-day band)."""
    assert ANNUAL_LEAVE_DAYS_UNDER_5YR == 21
    assert ANNUAL_LEAVE_DAYS_5YR_PLUS == 30
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_leave_balance(df)
    c7 = next(c for c in result.candidates if c.years_of_service == 7.0)
    assert c7.cumulative_entitlement_days == pytest.approx(165.0, abs=0.01)
    c12 = next(c for c in result.candidates if c.years_of_service == 12.0)
    assert c12.cumulative_entitlement_days == pytest.approx(315.0, abs=0.01)  # 5*21+7*30
    c1 = next(c for c in result.candidates if c.years_of_service == 1.0)
    assert c1.cumulative_entitlement_days == pytest.approx(21.0, abs=0.01)


def test_leave_compensation_uses_article_111_daily_wage_formula():
    """Article 111: daily wage = monthly wage / 30; compensation = daily
    wage x unused days. Employee with wage=10000, balance=40 days:
    (10000/30) * 40 = 333.33... * 40 = 13333.33."""
    assert LEAVE_COMPENSATION_DAY_DIVISOR == 30
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_leave_balance(df)
    c = next(c for c in result.candidates if c.years_of_service == 7.0)
    assert c.leave_balance_days == 40.0
    assert c.compensation_sar == pytest.approx((10000.0 / 30.0) * 40.0, abs=0.01)


def test_leave_no_balance_column_computes_entitlement_only():
    """Dropping the LeaveBalance column entirely must still compute
    entitlement accrual (from years of service alone) but MUST NOT compute
    any compensation figure — clearly distinguishing 'accrued since hire'
    from 'actual remaining balance', which requires data this upload
    doesn't have."""
    df = pd.read_csv(_CLEAN_FIXTURE).drop(columns=["LeaveBalance"])
    result = analyze_leave_balance(df)
    assert result.available is True
    assert result.has_real_balance_data is False
    assert all(c.leave_balance_days is None for c in result.candidates)
    assert all(c.compensation_sar is None for c in result.candidates)
    assert all(c.cumulative_entitlement_days > 0 for c in result.candidates)
    assert "entitlement" in result.narrative_en.lower()
    assert "not" in result.narrative_en.lower()  # "not actual remaining balance"


def test_leave_no_years_column_is_unavailable():
    df = pd.DataFrame({"EmployeeID": ["E1"], "MonthlySalary": [9000]})
    result = analyze_leave_balance(df)
    assert result.available is False


def test_leave_range_text_years_excludes_rows_not_guesses():
    """Same range-text discipline as gratuity, applied to years-of-service:
    'Less than 5 years' style values must never be guessed at a specific
    number."""
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2"],
        "YearsAtCompany": ["Less than 5 years", "From 5 to 10 years"],
        "MonthlySalary": [9000, 9500],
    })
    result = analyze_leave_balance(df)
    assert result.available is False


def test_unavailable_leave_result_never_fabricates():
    result = unavailable_leave_result("No years-of-service column detected.")
    assert result.available is False
    assert result.candidates == []


# ── 4. WPS consistency: real mismatches, three-way check, not-applicable ───

def test_wps_detects_real_mismatches_with_correct_amounts():
    df = pd.read_csv(_WPS_FIXTURE)
    result = analyze_wps_consistency(df)
    assert result.available is True
    assert result.check_applicable is True
    assert result.n_employees_checked == 5
    assert result.n_mismatches == 2
    diffs = {round(c.difference_sar, 2) for c in result.candidates}
    assert 500.0 in diffs    # E3: 10500 - 10000
    assert -2000.0 in diffs  # E4: 6000 - 8000


def test_wps_within_tolerance_not_flagged():
    """E2 (contract=10000, actual=10005, diff=5 SAR) is within the SAR-10
    absolute tolerance and must NOT appear in the mismatch list."""
    df = pd.read_csv(_WPS_FIXTURE)
    result = analyze_wps_consistency(df)
    flagged_diffs = {round(c.difference_sar, 2) for c in result.candidates}
    assert 5.0 not in flagged_diffs


def test_wps_three_way_base_plus_allowances_vs_total():
    """When basic + allowances + total are all present, the check must
    reconcile basic+allowances against total, not just basic against
    total directly."""
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3"],
        "BasicSalary": [8000, 8000, 8000],
        "Allowances": [2000, 2000, 2000],
        "TotalSalary": [10000, 10500, 9000],  # E1 matches, E2/E3 mismatch
    })
    result = analyze_wps_consistency(df)
    assert result.available is True
    assert result.n_mismatches == 2
    assert all(c.mismatch_type == "base_plus_allowances_vs_total" for c in result.candidates)
    assert all(c.expected_sar == 10000.0 for c in result.candidates)


def test_wps_single_salary_column_not_applicable():
    """test_employee_data.csv has exactly one salary-shaped column
    (MonthlyIncome) — the real, common case this session's fixtures
    established. Nothing to reconcile against, so the check must honestly
    report not-applicable rather than fabricating a mismatch."""
    df = pd.read_csv(_REAL_SINGLE_SALARY_FIXTURE)
    result = analyze_wps_consistency(df)
    assert result.available is False
    assert result.check_applicable is False
    assert "not" in result.reason.lower() or "only one" in result.reason.lower() or "1 salary" in result.reason.lower()


def test_unavailable_wps_result_never_fabricates():
    result = unavailable_wps_result("Only one salary column found.", check_applicable=False)
    assert result.available is False
    assert result.check_applicable is False
    assert result.candidates == []


# ── 5. PII safety: no raw employee ID ever appears in output ───────────────

def test_gratuity_output_includes_both_hash_and_raw_employee_id():
    """Phase 40 — deliberate reversal of the PII discipline every prior
    module this session established: this platform is used single-tenant
    on the uploader's own local data (not a shared/redistributed anonymized
    dataset), so the REAL uploaded ID is now included alongside
    record_id_safe (which is KEPT unchanged for cross-link joins) — see
    PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md §3 for the full
    reasoning and the modules that remain hash-only (EmployeeRiskDashboard,
    which has a real CSV export feature — the one genuine exception)."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_gratuity(df)
    d = gratuity_to_dict(result)
    raw_ids = set(df["EmployeeID"].astype(str))
    serialized = str(d)
    assert any(raw_id in serialized for raw_id in raw_ids), "Expected real employee IDs in gratuity output (Phase 40 decision)"
    assert all(c["record_id_safe"].startswith("EMP-") for c in d["candidates"])
    assert all(c["employee_id_raw"] in raw_ids for c in d["candidates"])


def test_leave_output_includes_both_hash_and_raw_employee_id():
    """Phase 40 — see test_gratuity_output_includes_both_hash_and_raw_employee_id
    docstring for the full reasoning."""
    df = pd.read_csv(_CLEAN_FIXTURE)
    result = analyze_leave_balance(df)
    d = leave_balance_to_dict(result)
    raw_ids = set(df["EmployeeID"].astype(str))
    serialized = str(d)
    assert any(raw_id in serialized for raw_id in raw_ids), "Expected real employee IDs in leave output (Phase 40 decision)"
    assert all(c["record_id_safe"].startswith("EMP-") for c in d["candidates"])
    assert all(c["employee_id_raw"] in raw_ids for c in d["candidates"])


# ── 6. Phase 23 regression: real-world column-name detection ───────────────
# The original _LEAVE_BALANCE_PATTERNS' trailing `\b` broke on PascalCase
# column names where a suffix word immediately follows the core keyword with
# no separator (e.g. "LeaveBalanceDays" — no boundary exists between
# "Balance" and "Days", both word characters) — live browser testing found
# this exact real column name went undetected, silently falling back to
# entitlement-only mode with zero compensation computed. See
# PHASE_23_LEAVE_BALANCE_DETECTION_FIX.md for the full root-cause trace.

@pytest.mark.parametrize("column_name", [
    "LeaveBalanceDays",       # the exact real-world name that failed
    "LeaveBalance",
    "AnnualLeaveBalance",
    "RemainingLeaveDays",
])
def test_leave_balance_column_detected_for_realistic_names(column_name):
    assert _LEAVE_BALANCE_PATTERNS.search(column_name) is not None, (
        f"{column_name!r} should be detected as a leave-balance column"
    )


@pytest.mark.parametrize("column_name", [
    "LeaveDaysTaken",
    "UsedLeaveDays",
    "LeaveDaysUsed",
    "LeaveTaken",
])
def test_leave_taken_column_detected_for_realistic_names(column_name):
    assert _LEAVE_TAKEN_PATTERNS.search(column_name) is not None, (
        f"{column_name!r} should be detected as a leave-taken column"
    )


def test_leave_balance_pattern_does_not_false_positive_on_unrelated_columns():
    """Broadening the pattern must not start matching genuinely unrelated
    columns."""
    for unrelated in ["LeaveType", "SickLeave", "MonthlySalary", "Department"]:
        assert _LEAVE_BALANCE_PATTERNS.search(unrelated) is None, (
            f"{unrelated!r} should NOT be detected as a leave-balance column"
        )
        assert _LEAVE_TAKEN_PATTERNS.search(unrelated) is None, (
            f"{unrelated!r} should NOT be detected as a leave-taken column"
        )


def test_leave_balance_days_column_now_detected_and_computes_real_figures():
    """End-to-end regression test using the exact reported fixture shape
    (180 rows, a 'LeaveBalanceDays' column, values 0-46) — must now detect
    the column and compute real, non-zero compensation figures instead of
    silently falling back to entitlement-only mode."""
    df = pd.read_csv(_LEAVE_BALANCE_DAYS_FIXTURE)
    result = analyze_leave_balance(df)
    assert result.available is True
    assert result.leave_balance_column == "LeaveBalanceDays"
    assert result.has_real_balance_data is True

    with_compensation = [c for c in result.candidates if c.compensation_sar is not None]
    assert len(with_compensation) > 0

    for c in with_compensation:
        expected = round((c.monthly_wage_sar / LEAVE_COMPENSATION_DAY_DIVISOR) * c.leave_balance_days, 2)
        assert c.compensation_sar == pytest.approx(expected, abs=0.01)

    # Employees with a 0-day balance must show SAR 0 compensation, not None
    # and not a fabricated positive figure.
    zero_balance = [c for c in result.candidates if c.leave_balance_days == 0]
    assert len(zero_balance) > 0
    assert all(c.compensation_sar == 0.0 for c in zero_balance)


# ── 6b. Phase 42 regression: LeaveDaysTakenThisYear column detection ───────
# QA-reported real column name that went undetected — same structural flaw
# as the Phase 23 balance-pattern bug (trailing `\b` breaks when a suffix
# word immediately follows the keyword with no separator). See
# PHASE_42_LEAVE_TAKEN_DETECTION_FIX.md for the full root-cause trace.

@pytest.mark.parametrize("column_name", [
    "LeaveDaysTakenThisYear",  # the exact reported real-world name
    "AnnualLeaveTaken",
    "LeaveTaken",
    "LeaveDaysTaken",
    "Leave_Taken",
    "LeaveDaysUsed",
    "UsedLeaveDays",
])
def test_leave_taken_column_detected_for_realistic_names_phase42(column_name):
    assert _LEAVE_TAKEN_PATTERNS.search(column_name) is not None, (
        f"{column_name!r} should be detected as a leave-taken column"
    )


def test_leave_taken_pattern_does_not_false_positive_on_unrelated_columns_phase42():
    """Adding the ThisYear/annual suffix-and-prefix handling must not start
    matching genuinely unrelated columns."""
    for unrelated in ["LeaveType", "SickLeave", "MonthlySalary", "Department", "TakenAt"]:
        assert _LEAVE_TAKEN_PATTERNS.search(unrelated) is None, (
            f"{unrelated!r} should NOT be detected as a leave-taken column"
        )


def test_leave_missing_taken_column_still_uses_entitlement_only_fallback():
    """No leave-balance or leave-taken column at all must still fall back to
    the pre-existing entitlement-only behavior (has_real_balance_data False,
    no fabricated compensation) — the Phase 42 fix must not change this."""
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2"],
        "YearsAtCompany": [3, 10],
        "MonthlySalary": [6000, 10000],
    })
    result = analyze_leave_balance(df)
    assert result.available is True
    assert result.leave_taken_column is None
    assert result.has_real_balance_data is False
    assert all(c.leave_balance_days is None for c in result.candidates)
    assert all(c.compensation_sar is None for c in result.candidates)


def test_leave_days_taken_this_year_end_to_end_multiple_employees():
    """End-to-end regression using the exact reported column name across a
    small controlled multi-employee dataset with hand-computed expected
    values, covering: normal case, zero taken, missing/blank taken, and
    leave-taken exceeding entitlement (must clamp compensation at 0, not go
    negative) — Phase 3 of the audit's required scenario list.

    Entitlement = years*21 for years<=5 (Article 109); compensation =
    (wage/30) * max(balance, 0) (Article 111). Neither formula is changed by
    this fix — only column detection.
    """
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3", "E4", "E5", "E6"],
        "YearsAtCompany": [3, 1, 10, 2, 4, 1],
        "MonthlySalary": [6000, 3000, 10000, 4000, 5000, 3000],
        "LeaveDaysTakenThisYear": [5, 0, 40, None, 0, 50],
    })
    result = analyze_leave_balance(df)
    assert result.available is True
    assert result.leave_taken_column == "LeaveDaysTakenThisYear"
    assert result.has_real_balance_data is True

    by_id = {c.employee_id_raw: c for c in result.candidates}

    # E1: entitlement 3*21=63, taken 5 -> balance 58, comp (6000/30)*58=11600
    c1 = by_id["E1"]
    assert c1.cumulative_entitlement_days == pytest.approx(63.0)
    assert c1.leave_balance_days == pytest.approx(58.0)
    assert c1.compensation_sar == pytest.approx(11600.0)

    # E2: entitlement 21, taken 0 -> balance 21, comp (3000/30)*21=2100
    c2 = by_id["E2"]
    assert c2.leave_balance_days == pytest.approx(21.0)
    assert c2.compensation_sar == pytest.approx(2100.0)

    # E3: entitlement 5*21+5*30=255, taken 40 -> balance 215,
    # comp (10000/30)*215 = 71666.67
    c3 = by_id["E3"]
    assert c3.cumulative_entitlement_days == pytest.approx(255.0)
    assert c3.leave_balance_days == pytest.approx(215.0)
    assert c3.compensation_sar == pytest.approx(71666.67, abs=0.01)

    # E4: missing/blank taken value -> no balance, no compensation computed
    # for this row (honest degradation, not a fabricated figure)
    c4 = by_id["E4"]
    assert c4.leave_balance_days is None
    assert c4.compensation_sar is None

    # E5: entitlement 84, taken 0 (explicit zero, not missing) -> balance 84,
    # comp (5000/30)*84=14000, must be a real number not None
    c5 = by_id["E5"]
    assert c5.leave_balance_days == pytest.approx(84.0)
    assert c5.compensation_sar == pytest.approx(14000.0)

    # E6: entitlement 21, taken 50 (exceeds entitlement) -> balance goes
    # negative (-29, disclosed as-is) but compensation must clamp at 0, not
    # go negative.
    c6 = by_id["E6"]
    assert c6.leave_balance_days == pytest.approx(-29.0)
    assert c6.compensation_sar == pytest.approx(0.0)


# ── 7. Phase 41: date-based tenure (exact Excel D15/F15 formula) ───────────
# Copy of EOS Report.xlsx's "New" sheet computes tenure as
# (LastWorkingDay - DateOfJoining + 1) / 365 — an exact day count, not a
# pre-rounded YearsAtCompany-style figure. See
# PHASE_28_EXACT_PRECISION_AND_DATE_BASED_TENURE.md and the module
# docstring's Phase 41 section.

@pytest.mark.parametrize("column_name", ["DateOfJoining", "HireDate", "Hire Date", "JoiningDate"])
def test_hire_date_column_detected_for_realistic_names(column_name):
    assert _HIRE_DATE_PATTERNS.search(column_name) is not None, (
        f"{column_name!r} should be detected as a hire-date column"
    )


@pytest.mark.parametrize("column_name", ["LastWorkingDay", "Last Working Day", "SeparationDate", "TerminationDate"])
def test_last_working_day_column_detected_for_realistic_names(column_name):
    assert _LAST_WORKING_DAY_PATTERNS.search(column_name) is not None, (
        f"{column_name!r} should be detected as a last-working-day column"
    )


@pytest.mark.parametrize("column_name", ["AsOfDate", "AnalysisDate", "ReportingDate", "SnapshotDate"])
def test_as_of_date_column_detected_for_realistic_names(column_name):
    assert _AS_OF_DATE_PATTERNS.search(column_name) is not None, (
        f"{column_name!r} should be detected as an as-of/snapshot date column"
    )


def test_gratuity_date_based_tenure_reproduces_exact_excel_worked_example():
    """The exact reference scenario re-verified live this session (join
    01/11/2022, last day 10/10/2026, salary 10425): the Excel 'New' sheet's
    formula chain gives years_of_service=3.9452054794520546,
    I15 (full award)=20564.38, I13 (1/3 resignation tier)=6854.79. Computed
    here purely from hire/last-working-day dates — no YearsAtCompany column
    supplied at all — to confirm the date-based path alone reproduces the
    already-Excel-matched figures exactly."""
    df = pd.DataFrame({
        "EmployeeID": ["NEWEMP001"],
        "Department": ["Operations"],
        "DateOfJoining": ["2022-11-01"],
        "LastWorkingDay": ["2026-10-10"],
        "MonthlySalary": [10425],
    })
    result = analyze_gratuity(df)
    assert result.available is True
    assert result.years_of_service_column is None
    assert result.hire_date_column == "DateOfJoining"
    assert result.last_working_day_column == "LastWorkingDay"
    assert result.n_tenure_computed_from_dates == 1
    c = result.candidates[0]
    assert c.years_of_service == pytest.approx(3.9452054794520546, abs=1e-9)
    assert c.gratuity_full_award_sar == pytest.approx(20564.38, abs=0.01)
    assert c.gratuity_if_resignation_sar == pytest.approx(6854.79, abs=0.01)


def test_leave_date_based_tenure_reproduces_exact_excel_worked_example():
    """Same reference scenario as the gratuity test above; Excel E19 (leave
    compensation) = 9524.975 for a 27.41-day balance."""
    df = pd.DataFrame({
        "EmployeeID": ["NEWEMP001"],
        "Department": ["Operations"],
        "DateOfJoining": ["2022-11-01"],
        "LastWorkingDay": ["2026-10-10"],
        "MonthlySalary": [10425],
        "LeaveBalance": [27.41],
    })
    result = analyze_leave_balance(df)
    assert result.available is True
    assert result.n_tenure_computed_from_dates == 1
    c = result.candidates[0]
    assert c.years_of_service == pytest.approx(3.9452054794520546, abs=1e-9)
    assert c.compensation_sar == pytest.approx(9524.98, abs=0.01)


def test_gratuity_falls_back_to_years_column_when_no_dates_present():
    """No hire/last-working-day columns at all — must still work exactly as
    before via the years-of-service column, and disclose zero date-derived
    rows."""
    df = pd.DataFrame({
        "EmployeeID": ["E1"],
        "Department": ["Ops"],
        "YearsAtCompany": [3.9],
        "MonthlySalary": [10425],
    })
    result = analyze_gratuity(df)
    assert result.available is True
    assert result.years_of_service_column == "YearsAtCompany"
    assert result.hire_date_column is None
    assert result.last_working_day_column is None
    assert result.n_tenure_computed_from_dates == 0
    assert result.candidates[0].years_of_service == 3.9


def test_gratuity_dates_take_priority_over_years_column_per_row():
    """When BOTH a years-of-service column and hire/last-working-day columns
    are present, the exact date-derived tenure wins for any row where both
    dates parse — the years-of-service column is only a per-row fallback for
    rows without a usable date pair (per PHASE_28's explicit priority
    requirement)."""
    df = pd.DataFrame({
        "EmployeeID": ["HAS_DATES", "NO_DATES"],
        "Department": ["Ops", "Ops"],
        "YearsAtCompany": [3.9, 5.0],          # deliberately "wrong"/stale for HAS_DATES
        "DateOfJoining": ["2022-11-01", None],
        "LastWorkingDay": ["2026-10-10", None],
        "MonthlySalary": [10425, 9000],
    })
    result = analyze_gratuity(df)
    assert result.n_tenure_computed_from_dates == 1
    by_id = {c.employee_id_raw: c for c in result.candidates}
    # Date-derived exact figure, NOT the stale 3.9 from YearsAtCompany.
    assert by_id["HAS_DATES"].years_of_service == pytest.approx(3.9452054794520546, abs=1e-9)
    # No usable dates for this row — falls back to the years column untouched.
    assert by_id["NO_DATES"].years_of_service == 5.0


def test_gratuity_as_of_date_used_as_end_date_for_still_active_employees():
    """No LastWorkingDay column, but an AsOfDate snapshot column stands in
    for it — still-active employees have no real separation date yet."""
    df = pd.DataFrame({
        "EmployeeID": ["E1"],
        "Department": ["Ops"],
        "DateOfJoining": ["2022-11-01"],
        "AsOfDate": ["2026-10-10"],
        "MonthlySalary": [10425],
    })
    result = analyze_gratuity(df)
    assert result.available is True
    assert result.last_working_day_column == "AsOfDate"
    assert result.candidates[0].years_of_service == pytest.approx(3.9452054794520546, abs=1e-9)


def test_gratuity_unparseable_dates_excluded_not_guessed():
    """A row with unparseable date values must be excluded (and counted),
    never silently guessed at some fallback tenure."""
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2"],
        "Department": ["Ops", "Ops"],
        "DateOfJoining": ["2022-11-01", "not a date"],
        "LastWorkingDay": ["2026-10-10", "also not a date"],
        "MonthlySalary": [10425, 9000],
    })
    result = analyze_gratuity(df)
    assert result.available is True
    assert result.n_valid_computed == 1
    assert result.n_excluded_invalid_years == 1
    assert result.candidates[0].employee_id_raw == "E1"


def test_gratuity_to_dict_serializes_date_based_tenure_fields():
    df = pd.DataFrame({
        "EmployeeID": ["NEWEMP001"],
        "Department": ["Operations"],
        "DateOfJoining": ["2022-11-01"],
        "LastWorkingDay": ["2026-10-10"],
        "MonthlySalary": [10425],
    })
    d = gratuity_to_dict(analyze_gratuity(df))
    assert d["hire_date_column"] == "DateOfJoining"
    assert d["last_working_day_column"] == "LastWorkingDay"
    assert d["n_tenure_computed_from_dates"] == 1


def test_leave_to_dict_serializes_date_based_tenure_fields():
    df = pd.DataFrame({
        "EmployeeID": ["NEWEMP001"],
        "Department": ["Operations"],
        "DateOfJoining": ["2022-11-01"],
        "LastWorkingDay": ["2026-10-10"],
        "MonthlySalary": [10425],
        "LeaveBalance": [27.41],
    })
    d = leave_balance_to_dict(analyze_leave_balance(df))
    assert d["hire_date_column"] == "DateOfJoining"
    assert d["last_working_day_column"] == "LastWorkingDay"
    assert d["n_tenure_computed_from_dates"] == 1


# ── 8. Phase 29: EMP0097 leave-compensation regression + leave/gratuity
#    date-priority parity ─────────────────────────────────────────────────
# A live-testing report claimed EMP0097 (Marketing, MonthlySalary=10425,
# LeaveBalance=27, YearsAtCompany=3.9 — the years-column fallback path, no
# date columns) produced compensation_sar=9363.60 instead of the
# Excel-formula-correct 9382.50 (=10425/30*27). Investigated thoroughly:
# re-opened Copy of EOS Report.xlsx and re-confirmed E19=F13/30*D19 with
# F13 a direct, unadjusted salary input (no housing-allowance term, no
# alternate divisor); read analyze_leave_balance()'s compensation step
# line-by-line (labor_law_calculators.py ~1204-1208: `daily_wage =
# wage / LEAVE_COMPENSATION_DAY_DIVISOR; compensation = round(daily_wage *
# max(leave_balance_days, 0.0), 2)`) and confirmed it matches E19 exactly;
# confirmed _resolve_years_of_service() is ALREADY the single shared helper
# both analyze_gratuity() (line 661) and analyze_leave_balance() (line 1180)
# call — not two diverging implementations; confirmed the route-layer
# preprocessing step only renames/strips COLUMN NAMES, never touches cell
# values; and reproduced this exact scenario against the live, freshly
# restarted API (POST /api/local/leave-balance-calculator) — it returned
# compensation_sar=9382.5, the CORRECT figure, not 9363.60. The discrepancy
# could not be reproduced anywhere in the current codebase; see
# PHASE_29_LEAVE_COMPENSATION_FIX_AND_DATE_CONSISTENCY.md for the full
# trace. These tests lock in the correct figure as a regression guard
# regardless, and close the one genuine coverage gap found along the way:
# Leave Balance had no per-row date-vs-years-column priority test, even
# though Gratuity did (test_gratuity_dates_take_priority_over_years_column_per_row).

def test_leave_emp0097_reported_scenario_produces_excel_correct_compensation():
    """Exact reported scenario: Marketing dept, MonthlySalary=10425,
    LeaveBalance=27, YearsAtCompany=3.9 (years-column fallback path, no
    date columns supplied). Excel formula: 10425/30*27 = 9382.50."""
    df = pd.DataFrame({
        "EmployeeID": ["EMP0097"],
        "Department": ["Marketing"],
        "YearsAtCompany": [3.9],
        "MonthlySalary": [10425],
        "LeaveBalance": [27],
    })
    result = analyze_leave_balance(df)
    assert result.available is True
    assert result.hire_date_column is None
    assert result.last_working_day_column is None
    c = result.candidates[0]
    assert c.employee_id_raw == "EMP0097"
    assert c.years_of_service == 3.9
    assert c.cumulative_entitlement_days == pytest.approx(81.9, abs=0.01)
    assert c.monthly_wage_sar == 10425.0
    assert c.leave_balance_days == 27.0
    assert c.compensation_sar == pytest.approx(9382.50, abs=0.01)


def test_leave_dates_take_priority_over_years_column_per_row():
    """Leave-balance equivalent of
    test_gratuity_dates_take_priority_over_years_column_per_row — closes
    the coverage gap: when BOTH a years-of-service column and hire/
    last-working-day columns are present, the exact date-derived tenure
    must win for entitlement AND compensation alike, per row, exactly as
    it already does for Gratuity."""
    df = pd.DataFrame({
        "EmployeeID": ["HAS_DATES", "NO_DATES"],
        "Department": ["Ops", "Ops"],
        "YearsAtCompany": [3.9, 5.0],           # deliberately "wrong"/stale for HAS_DATES
        "DateOfJoining": ["2022-11-01", None],
        "LastWorkingDay": ["2026-10-10", None],
        "MonthlySalary": [10425, 9000],
        "LeaveBalance": [27.41, 30],
    })
    result = analyze_leave_balance(df)
    assert result.n_tenure_computed_from_dates == 1
    by_id = {c.employee_id_raw: c for c in result.candidates}

    # Date-derived full-precision tenure, NOT the stale rounded 3.9 —
    # identical precision to Gratuity's own date-based path.
    assert by_id["HAS_DATES"].years_of_service == pytest.approx(3.9452054794520546, abs=1e-9)
    # cumulative_entitlement_days is rounded to 1 decimal place for display
    # (same rounding every other entitlement test in this file expects).
    assert by_id["HAS_DATES"].cumulative_entitlement_days == pytest.approx(
        round(3.9452054794520546 * ANNUAL_LEAVE_DAYS_UNDER_5YR, 1), abs=0.01
    )
    assert by_id["HAS_DATES"].compensation_sar == pytest.approx(9524.98, abs=0.01)

    # No usable dates for this row — falls back to the years column untouched.
    assert by_id["NO_DATES"].years_of_service == 5.0
    assert by_id["NO_DATES"].cumulative_entitlement_days == pytest.approx(
        round(5.0 * ANNUAL_LEAVE_DAYS_UNDER_5YR, 1), abs=0.01
    )
    assert by_id["NO_DATES"].compensation_sar == pytest.approx((9000 / 30) * 30, abs=0.01)
