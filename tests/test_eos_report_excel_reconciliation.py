"""
Phase 39 — Reconciliation against the user's authoritative reference file
`Copy of EOS Report.xlsx` (repo root).

The file was opened with `openpyxl` in BOTH formula mode (`data_only=False`)
and values mode (`data_only=True`) to extract the exact formula structure,
not just displayed numbers — see PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md
§1 for the full cell-by-cell dump and comparison.

**Result: the Article 84 base-formula and Article 85 resignation-tier logic
already in `labor_law_calculators.py` were found to be an EXACT match** to
every one of the workbook's 4 gratuity worksheets (`نموذج يدوي`,
`نهاية الخدمة`, `EOS C`, `New`) and its Article 111 leave-compensation
formula — confirmed bit-for-bit (to floating-point precision) against three
of the workbook's own real worked examples, encoded below as fixture rows
so this match is locked in as a regression test, not just a one-time manual
check.

**The one real gap found**: the workbook's own "Type" selector lists three
separation types — `Resignation`, `Termination (80)`, `EndOfContract` — but
the prior code only ever recognized two (resignation vs. "any other
termination = full award"), silently absorbing "Termination (80)" into the
ordinary full-award bucket via a substring match on "termination". Live
research confirmed Article 80 for-cause dismissals are a real legal
forfeiture case, not a synonym for ordinary termination — see
`labor_law_calculators.py`'s `_ARTICLE_80_TOKENS` and `GRATUITY_SOURCES`'
Article 80 entry for the full citation and the explicit caveat that this
provision is sourced from secondary law-firm summaries, not a directly-
quoted statute excerpt (unlike Articles 84/85), and is therefore NEVER
auto-applied to `applicable_amount_sar` — only disclosed separately via
`article_80_reduced_award_sar`.

Run: py -m pytest tests/test_eos_report_excel_reconciliation.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.labor_law_calculators import (
    analyze_gratuity,
    analyze_leave_balance,
)

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _ROOT / "eos_report_reconciliation_test_data.csv"


def _load() -> pd.DataFrame:
    return pd.read_csv(_FIXTURE)


class TestExcelWorkedExamplesReconciliation:
    """Each test below reproduces one real row from `Copy of EOS Report.xlsx`
    and asserts the platform's output matches the workbook's own computed
    value to the cent (allowing only float rounding tolerance)."""

    def test_sheet_nihayat_alkhidma_amal_alshamry(self):
        """Sheet 'نهاية الخدمة' (the most complete worked example): salary
        11081, tenure 1869 days / 365 = 5.120547945205479 years, Resignation.
        Excel E23 (base) = 29038.291780821917; F23 (E23*F12, F12=2/3) =
        19358.861187214592."""
        df = _load()
        result = analyze_gratuity(df)
        c = next(cd for cd in result.candidates if cd.record_id_safe and cd.monthly_wage_sar == 11081.0)
        assert c.years_of_service == pytest.approx(5.120547945205479, abs=1e-9)
        assert c.gratuity_full_award_sar == pytest.approx(29038.29, abs=0.01)
        assert c.separation_type == "resignation"
        assert c.applicable_scenario == "resignation"
        assert c.applicable_amount_sar == pytest.approx(19358.86, abs=0.01)

    def test_sheet_eos_c_exact_5_year_boundary(self):
        """Sheet 'EOS C': salary 7000, tenure hardcoded at exactly 1825 days
        (= 5.0 years exactly) — Excel's own IF(days<=1825, ...) boundary
        test. G15/D20 (base) = 17500 exactly (5 years * 0.5 * salary, the
        <=5-year branch, not the >5-year branch)."""
        df = _load()
        result = analyze_gratuity(df)
        c = next(cd for cd in result.candidates if cd.monthly_wage_sar == 7000.0)
        assert c.years_of_service == pytest.approx(5.0, abs=1e-9)
        assert c.gratuity_full_award_sar == pytest.approx(17500.0, abs=0.01)

    def test_sheet_eos_c_leave_compensation(self):
        """Same 'EOS C' sheet: D19 = D13/30*B19 = 7000/30*18 = 4200 exactly
        — Article 111's daily-wage-over-30 formula applied to 18 leave days."""
        df = _load()
        result = analyze_leave_balance(df)
        c = next(cd for cd in result.candidates if cd.monthly_wage_sar == 7000.0)
        assert c.leave_balance_days == pytest.approx(18.0, abs=1e-9)
        assert c.compensation_sar == pytest.approx(4200.0, abs=0.01)

    def test_sheet_new_under_5_years_with_both_fractions(self):
        """Sheet 'New': salary 10425, tenure 1410 days / 365 =
        3.863013698630137 years (<=5, so the short-tenure-only formula
        branch). I15 (base) = 20135.95890410959; I13 (base*1/3) =
        6711.986294657877; I14 (base*2/3) = 13423.972602739712 — this
        employee's SeparationType is Resignation and tenure falls in the
        2-5 year Article 85 tier, so the APPLICABLE figure must be the
        one-third value, matching I13."""
        df = _load()
        result = analyze_gratuity(df)
        c = next(cd for cd in result.candidates if cd.monthly_wage_sar == 10425.0)
        assert c.years_of_service == pytest.approx(3.863013698630137, abs=1e-9)
        assert c.gratuity_full_award_sar == pytest.approx(20135.96, abs=0.01)
        assert c.gratuity_if_resignation_sar == pytest.approx(6711.99, abs=0.01)  # I13: base * 1/3
        assert c.applicable_amount_sar == pytest.approx(6711.99, abs=0.01)

    def test_sheet_new_leave_compensation_fractional_days(self):
        """Same 'New' sheet: E19 = F13/30*D19 = 10425/30*27.41 = 9524.975 —
        confirms fractional (non-integer) leave-day counts are handled
        identically to the Excel's own fractional D19=27.41 input."""
        df = _load()
        result = analyze_leave_balance(df)
        c = next(cd for cd in result.candidates if cd.monthly_wage_sar == 10425.0)
        assert c.leave_balance_days == pytest.approx(27.41, abs=1e-9)
        assert c.compensation_sar == pytest.approx(9524.975, abs=0.01)


class TestArticle80Reconciliation:
    """The one real gap the Excel comparison found: 'Termination (80)' is a
    third, distinct separation type in the workbook's own Type selector,
    not a synonym for ordinary termination."""

    def test_termination_80_detected_as_distinct_from_ordinary_termination(self):
        df = _load()
        result = analyze_gratuity(df)
        art80_candidates = [c for c in result.candidates if c.separation_type == "termination_for_cause_article_80"]
        assert len(art80_candidates) == 2  # EOSEMP004, EOSEMP005

    def test_termination_80_under_5_years_reduced_award_is_zero(self):
        df = _load()
        result = analyze_gratuity(df)
        c = next(cd for cd in result.candidates if cd.monthly_wage_sar == 9000.0 and cd.years_of_service == 3.0)
        assert c.separation_type == "termination_for_cause_article_80"
        assert c.article_80_reduced_award_sar == 0.0
        # Never auto-reduced — applicable_amount_sar stays the full award.
        assert c.applicable_amount_sar == pytest.approx(13500.0, abs=0.01)  # 9000*3*0.5
        assert c.applicable_scenario == "termination_for_cause_article_80_flagged"

    def test_termination_80_at_5_plus_years_reduced_award_is_half(self):
        df = _load()
        result = analyze_gratuity(df)
        c = next(cd for cd in result.candidates if cd.monthly_wage_sar == 9000.0 and cd.years_of_service == 8.0)
        # base = 9000*5*0.5 + 9000*3*1.0 = 22500 + 27000 = 49500
        assert c.gratuity_full_award_sar == pytest.approx(49500.0, abs=0.01)
        assert c.article_80_reduced_award_sar == pytest.approx(24750.0, abs=0.01)  # half
        # Still never auto-reduced.
        assert c.applicable_amount_sar == pytest.approx(49500.0, abs=0.01)

    def test_ordinary_termination_tokens_unaffected_by_article_80_addition(self):
        """A plain 'Termination' (no '(80)') must still classify as ordinary
        full-award termination, not Article 80 — confirms the substring-
        match ordering fix didn't overcorrect."""
        df = pd.DataFrame({
            "EmployeeID": ["X1"], "Department": ["Ops"], "YearsAtCompany": [4],
            "MonthlySalary": [8000], "SeparationType": ["Termination"],
        })
        result = analyze_gratuity(df)
        c = result.candidates[0]
        assert c.separation_type == "employer_termination_or_end_of_contract"
        assert c.article_80_reduced_award_sar is None
        assert c.applicable_scenario == "full_termination"

    def test_gratuity_to_dict_serializes_article_80_field(self):
        from backend.core.labor_law_calculators import gratuity_to_dict
        df = _load()
        result = analyze_gratuity(df)
        d = gratuity_to_dict(result)
        art80 = [c for c in d["candidates"] if c["separation_type"] == "termination_for_cause_article_80"]
        assert len(art80) == 2
        assert all("article_80_reduced_award_sar" in c for c in d["candidates"])
