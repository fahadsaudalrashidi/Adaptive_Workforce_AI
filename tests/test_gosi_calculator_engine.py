"""
Phase 37 — GOSI Contribution Calculator tests.

Real government social-insurance contribution amounts, not illustrative
estimates. Every hand-computed test below uses the current-period rates
(July-December 2026): Old System 21.5% (9.75% employee / 11.75% employer),
New System 23.5% (10.75% employee / 12.75% employer), non-Saudi 2%
employer-only, contribution base capped at SAR 45,000/month.

Run: py -m pytest tests/test_gosi_calculator_engine.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.gosi_calculator_engine import (
    GOSI_WAGE_CAP_SAR,
    NEW_SYSTEM_EMPLOYEE_RATE,
    NEW_SYSTEM_EMPLOYER_RATE,
    NON_SAUDI_EMPLOYER_RATE,
    OLD_SYSTEM_EMPLOYEE_RATE,
    OLD_SYSTEM_EMPLOYER_RATE,
    analyze_gosi_contributions,
    gosi_result_to_dict,
    unavailable_gosi_result,
)

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _ROOT / "gosi_calculator_test_data.csv"
_NO_NATIONALITY_FIXTURE = _ROOT / "test_employee_data.csv"


def _load() -> pd.DataFrame:
    return pd.read_csv(_FIXTURE)


class TestBasicAvailability:
    def test_real_fixture_available_and_counts(self):
        r = analyze_gosi_contributions(_load())
        assert r.available is True
        assert r.n_employees_total == 7
        assert r.n_valid_computed == 5
        assert r.n_excluded_invalid_salary == 1
        assert r.n_excluded_unclassifiable_nationality == 1

    def test_missing_nationality_column_unavailable(self):
        r = analyze_gosi_contributions(pd.read_csv(_NO_NATIONALITY_FIXTURE))
        assert r.available is False
        assert r.columns_detected["nationality"] is False

    def test_empty_dataframe_unavailable(self):
        r = analyze_gosi_contributions(pd.DataFrame())
        assert r.available is False

    def test_unavailable_helper_never_raises(self):
        r = unavailable_gosi_result("no data")
        assert r.available is False
        assert r.candidates == []


class TestHandComputedFigures:
    def _candidate(self, r, emp_id_hash_of):
        """Find candidate by matching subject wage (unique per row in this fixture)."""
        return next(c for c in r.candidates if c.subject_wage_sar == emp_id_hash_of)

    def test_old_system_saudi_employee(self):
        r = analyze_gosi_contributions(_load())
        c = self._candidate(r, 12000.0)  # GEMP001: 10000 + 2000 housing
        assert c.is_saudi is True
        assert c.applicable_system == "old"
        assert c.old_system_employee_sar == pytest.approx(12000 * OLD_SYSTEM_EMPLOYEE_RATE)
        assert c.old_system_employer_sar == pytest.approx(12000 * OLD_SYSTEM_EMPLOYER_RATE)
        assert c.applicable_employee_sar == pytest.approx(1170.0)
        assert c.applicable_employer_sar == pytest.approx(1410.0)
        assert c.applicable_total_sar == pytest.approx(2580.0)
        assert c.subject_wage_capped is False

    def test_new_system_saudi_employee(self):
        r = analyze_gosi_contributions(_load())
        c = self._candidate(r, 18000.0)  # GEMP002: 15000 + 3000 housing
        assert c.applicable_system == "new"
        assert c.new_system_employee_sar == pytest.approx(18000 * NEW_SYSTEM_EMPLOYEE_RATE)
        assert c.new_system_employer_sar == pytest.approx(18000 * NEW_SYSTEM_EMPLOYER_RATE)
        assert c.applicable_total_sar == pytest.approx(4230.0)

    def test_non_saudi_employee_employer_only_2pct(self):
        r = analyze_gosi_contributions(_load())
        c = self._candidate(r, 9500.0)  # GEMP003: 8000 + 1500 housing
        assert c.is_saudi is False
        assert c.applicable_system == "non_saudi"
        assert c.applicable_employee_sar == 0.0
        assert c.applicable_employer_sar == pytest.approx(9500 * NON_SAUDI_EMPLOYER_RATE)
        assert c.old_system_total_sar is None
        assert c.new_system_total_sar is None

    def test_wage_cap_applied_and_flagged(self):
        r = analyze_gosi_contributions(_load())
        # GEMP004: 40000 + 10000 = 50000 raw, capped at 45000
        c = self._candidate(r, GOSI_WAGE_CAP_SAR)
        assert c.subject_wage_capped is True
        assert c.subject_wage_sar == GOSI_WAGE_CAP_SAR
        assert c.applicable_system == "unspecified_both_shown"
        # Conservative default: New System used as applicable when unspecified
        assert c.applicable_employee_sar == pytest.approx(45000 * NEW_SYSTEM_EMPLOYEE_RATE)
        assert c.applicable_employer_sar == pytest.approx(45000 * NEW_SYSTEM_EMPLOYER_RATE)
        # Both scenarios still exposed, never hidden
        assert c.old_system_total_sar == pytest.approx(45000 * (OLD_SYSTEM_EMPLOYEE_RATE + OLD_SYSTEM_EMPLOYER_RATE))
        assert c.new_system_total_sar == pytest.approx(45000 * (NEW_SYSTEM_EMPLOYEE_RATE + NEW_SYSTEM_EMPLOYER_RATE))

    def test_non_saudi_no_housing_column_uses_salary_only(self):
        r = analyze_gosi_contributions(_load())
        c = self._candidate(r, 20000.0)  # GEMP005: 20000 salary + 0 housing
        assert c.applicable_employer_sar == pytest.approx(20000 * NON_SAUDI_EMPLOYER_RATE)

    def test_range_text_salary_excluded_not_approximated(self):
        r = analyze_gosi_contributions(_load())
        # GEMP006 has range-text salary "From 5000 to 8000" -> excluded entirely
        assert all(c.subject_wage_sar != pytest.approx(6000 + 1000) for c in r.candidates)
        assert r.example_excluded_salary_value == "From 5000 to 8000"

    def test_missing_nationality_row_excluded(self):
        r = analyze_gosi_contributions(_load())
        # GEMP007 has blank nationality -> excluded despite valid salary/housing
        assert all(c.subject_wage_sar != pytest.approx(14000.0) for c in r.candidates)


class TestDepartmentRollup:
    def test_department_breakdown_sums_correctly(self):
        r = analyze_gosi_contributions(_load())
        finance = next(d for d in r.department_breakdown if d.department == "Finance")
        # Finance = GEMP001 (old, 1170/1410) + GEMP004 (unspecified->new, 4837.5/5737.5)
        assert finance.n_employees == 2
        assert finance.total_employee_contribution_sar == pytest.approx(1170.0 + 45000 * NEW_SYSTEM_EMPLOYEE_RATE)
        assert finance.total_employer_contribution_sar == pytest.approx(1410.0 + 45000 * NEW_SYSTEM_EMPLOYER_RATE)

    def test_department_normalizer_reused(self):
        """Confirms department_normalizer.py is genuinely invoked (not a
        hardcoded passthrough): 'IT' and 'HR' abbreviations in the fixture
        are expanded to their canonical curated labels, proving real reuse
        of that module's synonym table rather than a raw passthrough."""
        r = analyze_gosi_contributions(_load())
        depts = {d.department for d in r.department_breakdown}
        assert depts == {"Finance", "Information Technology", "Sales", "Human Resources"}


class TestSerializationAndPII:
    def test_to_dict_serializes(self):
        r = analyze_gosi_contributions(_load())
        d = gosi_result_to_dict(r)
        assert d["available"] is True
        assert len(d["candidates"]) == 5
        assert "effective_period" in d
        assert d["wage_cap_sar"] == GOSI_WAGE_CAP_SAR

    def test_record_id_safe_stays_a_hash(self):
        r = analyze_gosi_contributions(_load())
        for c in r.candidates:
            assert not c.record_id_safe.startswith("GEMP")
            assert c.record_id_safe.startswith("EMP-") or c.record_id_safe.startswith("ROW-")

    def test_employee_id_raw_populated_phase_40(self):
        """Phase 40 — see PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md
        §3: this platform is single-tenant/local, so the real uploaded ID is
        now included alongside record_id_safe (kept for cross-link joins)."""
        r = analyze_gosi_contributions(_load())
        raw_ids = {c.employee_id_raw for c in r.candidates}
        assert raw_ids == {"GEMP001", "GEMP002", "GEMP003", "GEMP004", "GEMP005"}

    def test_housing_understated_note_present_when_no_housing_column(self):
        df = _load().drop(columns=["HousingAllowance"])
        r = analyze_gosi_contributions(df)
        assert r.housing_allowance_understated_note is not None


class TestPhase40IndependentReaudit:
    """Phase 40 — the user reported the GOSI calculator's output as incorrect
    with no specific example given. A rigorous independent re-audit was
    performed: rates re-verified via 3 fresh live searches (separate from
    Phase 25/37's original research), then these 4 scenarios were hand-
    computed independently and compared against the live engine's actual
    output. All 4 matched exactly — no discrepancy was found. See
    PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md §2 for the full
    audit trail and sources. These scenarios are locked in here as a
    permanent regression so this specific audit can't silently regress."""

    def _df(self):
        return pd.DataFrame({
            "EmployeeID": ["A1", "A2", "A3", "A4"],
            "Department": ["Finance"] * 4,
            "Nationality": ["Saudi", "Saudi", "Saudi", "Non-Saudi"],
            "MonthlySalary": [10000, 30000, 40000, 25000],
            "HousingAllowance": [2000, 8000, 10000, 5000],
            "GOSISystem": ["Old System", "New System", "", ""],
        })

    def test_saudi_old_system_under_cap(self):
        """A1: 10000 + 2000 housing = 12000 subject wage, Old System."""
        r = analyze_gosi_contributions(self._df())
        c = next(x for x in r.candidates if x.subject_wage_sar == 12000.0)
        assert c.applicable_system == "old"
        assert c.applicable_employee_sar == pytest.approx(12000 * OLD_SYSTEM_EMPLOYEE_RATE)  # 1170.0
        assert c.applicable_employer_sar == pytest.approx(12000 * OLD_SYSTEM_EMPLOYER_RATE)  # 1410.0

    def test_saudi_new_system_under_cap(self):
        """A2: 30000 + 8000 housing = 38000 subject wage, New System."""
        r = analyze_gosi_contributions(self._df())
        c = next(x for x in r.candidates if x.subject_wage_sar == 38000.0)
        assert c.applicable_system == "new"
        assert c.applicable_employee_sar == pytest.approx(38000 * NEW_SYSTEM_EMPLOYEE_RATE)  # 4085.0
        assert c.applicable_employer_sar == pytest.approx(38000 * NEW_SYSTEM_EMPLOYER_RATE)  # 4845.0

    def test_saudi_unspecified_system_capped(self):
        """A3: 40000 + 10000 housing = 50000 raw, capped to 45000. Cap is
        applied to the COMBINED basic+housing figure, not basic alone —
        the specific bug class the brief asked to check for."""
        r = analyze_gosi_contributions(self._df())
        c = next(x for x in r.candidates if x.subject_wage_sar == 45000.0 and x.is_saudi)
        assert c.subject_wage_capped is True
        assert c.old_system_total_sar == pytest.approx(45000 * (OLD_SYSTEM_EMPLOYEE_RATE + OLD_SYSTEM_EMPLOYER_RATE))  # 9675.0
        assert c.new_system_total_sar == pytest.approx(45000 * (NEW_SYSTEM_EMPLOYEE_RATE + NEW_SYSTEM_EMPLOYER_RATE))  # 10575.0

    def test_non_saudi_employer_only(self):
        """A4: 25000 + 5000 housing = 30000 subject wage, non-Saudi — 0%
        employee, 2% employer only, no old/new system distinction applies."""
        r = analyze_gosi_contributions(self._df())
        c = next(x for x in r.candidates if not x.is_saudi)
        assert c.subject_wage_sar == 30000.0
        assert c.applicable_employee_sar == 0.0
        assert c.applicable_employer_sar == pytest.approx(30000 * NON_SAUDI_EMPLOYER_RATE)  # 600.0
        assert c.old_system_total_sar is None
        assert c.new_system_total_sar is None
