"""
Phase 17 — Pay Equity Analysis engine tests.

Covers, each with real computed-value assertions (not smoke-only tests):
  1. A realistic fixture (pay_equity_realistic_test_data.csv, 400 rows,
     Department/JobLevel/Gender/MonthlyIncome) — gaps and p-values are
     independently recomputed from the CSV via pandas + scipy in this test
     file and compared exactly against the engine's output, across both a
     statistically significant cohort and a non-significant ("plausibly
     noise") cohort in the SAME dataset.
  2. Minimum-group-size suppression — a comparison with fewer than the
     reused `_MIN_GROUP_SIZE_FOR_DISPARITY` (20) per group must never be
     reported.
  3. High-cardinality bucketing reuse — Age (many distinct values) must be
     quantile-bucketed via the reused `_bucket_or_skip_for_disparity`
     rather than compared on raw values, exactly as ethical_ai.py does.
  4. Honest "not detected" degradation — datasets missing salary, a
     protected attribute, or any comparability factor must return
     available=False with no fabricated gap, listing which columns would
     activate the feature.
  5. Department-fallback-to-job-level behaviour on real, evenly-spread data.

Run: py -m pytest tests/test_pay_equity_engine.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scipy import stats as scipy_stats

from backend.core.ethical_ai import _MIN_GROUP_SIZE_FOR_DISPARITY, _SIGNIFICANCE_ALPHA
from backend.core.pay_equity_engine import (
    PAY_EQUITY_CONFIDENCE,
    analyze_pay_equity,
    pay_equity_to_dict,
    unavailable_pay_equity_result,
)

_ROOT = Path(__file__).resolve().parent.parent
_REALISTIC_FIXTURE = _ROOT / "pay_equity_realistic_test_data.csv"


@pytest.fixture(scope="module")
def realistic_df() -> pd.DataFrame:
    return pd.read_csv(_REALISTIC_FIXTURE)


@pytest.fixture(scope="module")
def realistic_result(realistic_df):
    return analyze_pay_equity(realistic_df)


# ── 1. Real computed-value assertions against independent recomputation ────

def _independent_gender_gap(df: pd.DataFrame, job_level: int) -> tuple[float, float, int, int, float, float]:
    """Recompute, independently of the engine, the higher-vs-lower-paid
    gender gap and Welch's t-test p-value for one job level — mirrors
    exactly what the engine is expected to compute (gap is always expressed
    as (higher - lower) / higher, whichever group actually pays more in
    that cohort — not a fixed "Male minus Female" direction), using
    pandas/scipy directly rather than calling any engine code."""
    sub = df[df["JobLevel"] == job_level]
    male = sub[sub["Gender"] == "Male"]["MonthlyIncome"]
    female = sub[sub["Gender"] == "Female"]["MonthlyIncome"]
    if male.mean() >= female.mean():
        hi, lo = male, female
    else:
        hi, lo = female, male
    gap_pct = round((hi.mean() - lo.mean()) / hi.mean() * 100, 1)
    _t, p = scipy_stats.ttest_ind(hi, lo, equal_var=False)
    return gap_pct, round(float(p), 4), len(male), len(female), round(male.mean(), 0), round(female.mean(), 0)


def test_job_level_4_significant_gap_matches_independent_recomputation(realistic_df, realistic_result):
    gap_pct, p_value, n_male, n_female, mean_male, mean_female = _independent_gender_gap(realistic_df, 4)
    assert p_value < _SIGNIFICANCE_ALPHA  # confirm this cohort really is significant before asserting on it

    match = [c for c in realistic_result.comparisons if c.cohort_label_en == "Job Level 4"]
    assert len(match) == 1
    c = match[0]
    assert c.higher_paid_group == "Male"
    assert c.lower_paid_group == "Female"
    assert c.higher_paid_group_n == n_male
    assert c.lower_paid_group_n == n_female
    assert c.higher_paid_group_mean_sar == mean_male
    assert c.lower_paid_group_mean_sar == mean_female
    assert c.pay_gap_pct == gap_pct
    assert c.p_value == p_value
    assert c.statistically_significant is True
    assert "statistically significant" in c.interpretation_en.lower()


def test_job_level_1_near_zero_gap_is_not_significant(realistic_df, realistic_result):
    gap_pct, p_value, *_ = _independent_gender_gap(realistic_df, 1)
    assert p_value >= _SIGNIFICANCE_ALPHA  # confirm this cohort really is noise-level before asserting on it

    match = [c for c in realistic_result.comparisons if c.cohort_label_en == "Job Level 1"]
    assert len(match) == 1
    c = match[0]
    assert c.pay_gap_pct == gap_pct
    assert c.p_value == p_value
    assert c.statistically_significant is False
    assert "not statistically significant" in c.interpretation_en.lower()
    assert "plausibly sampling noise" in c.interpretation_en.lower()


def test_all_four_computable_job_levels_present_none_fabricated(realistic_result):
    # Job Level 5 (n=16 Female / 12 Male) is below the size floor on both
    # sides and must be suppressed, not reported with a possibly-noisy gap.
    labels = {c.cohort_label_en for c in realistic_result.comparisons}
    assert labels == {"Job Level 1", "Job Level 2", "Job Level 3", "Job Level 4"}
    assert realistic_result.n_comparisons_suppressed_small_sample >= 1


# ── 2. Minimum-group-size suppression (reused from ethical_ai.py) ──────────

def test_min_group_size_suppression_when_group_too_small():
    # 25 Male + 8 Female in one job level — Female fails the reused
    # _MIN_GROUP_SIZE_FOR_DISPARITY=20 floor. No comparison should be
    # produced, but it must be counted as suppressed, not silently dropped.
    n_male, n_female = 25, 8
    df = pd.DataFrame({
        "MonthlyIncome": [10_000] * n_male + [8_000] * n_female,
        "Gender": ["Male"] * n_male + ["Female"] * n_female,
        "JobLevel": [1] * (n_male + n_female),
    })
    result = analyze_pay_equity(df)
    assert result.available is True
    assert result.comparisons == []
    assert result.n_comparisons_suppressed_small_sample == 1


def test_both_groups_meeting_floor_exactly_at_boundary_is_not_suppressed():
    n = _MIN_GROUP_SIZE_FOR_DISPARITY  # 20
    df = pd.DataFrame({
        "MonthlyIncome": [10_000] * n + [7_000] * n,
        "Gender": ["Male"] * n + ["Female"] * n,
        "JobLevel": [1] * (2 * n),
    })
    result = analyze_pay_equity(df)
    assert result.n_comparisons_computed == 1
    assert result.comparisons[0].higher_paid_group_n == n
    assert result.comparisons[0].lower_paid_group_n == n


# ── 3. High-cardinality bucketing reused from ethical_ai.py ────────────────

def test_high_cardinality_age_attribute_is_bucketed_not_raw(realistic_df):
    df = realistic_df.copy()
    # Give Age enough distinct values to trigger ethical_ai.py's bucketing
    # guard (_MAX_DISTINCT_VALUES_FOR_RAW_GROUPING=8) rather than comparing
    # 400 near-unique raw ages directly.
    import numpy as np
    rng = np.random.default_rng(7)
    df["Age"] = rng.integers(22, 60, size=len(df))
    result = analyze_pay_equity(df)
    age_comparisons = [c for c in result.comparisons if c.protected_attribute == "Age"]
    assert any(c.was_bucketed for c in age_comparisons) or any(
        "bucketed" in n.lower() for n in result.granularity_notes
    )


# ── 4. Honest "not detected" degradation — never fabricate ─────────────────

def test_unavailable_when_no_salary_column():
    df = pd.DataFrame({
        "Gender": ["Male", "Female"] * 15,
        "JobLevel": [1, 2] * 15,
    })
    result = analyze_pay_equity(df)
    assert result.available is False
    assert "salary" in result.reason.lower()
    assert result.columns_detected["salary_or_compensation"] is False
    assert result.comparisons == []


def test_unavailable_when_no_protected_attribute():
    df = pd.DataFrame({
        "MonthlyIncome": [10_000] * 30,
        "JobLevel": [1] * 30,
    })
    result = analyze_pay_equity(df)
    assert result.available is False
    assert result.columns_detected["protected_attribute"] is False


def test_unavailable_when_no_comparability_factor():
    df = pd.DataFrame({
        "MonthlyIncome": [10_000] * 30,
        "Gender": ["Male", "Female"] * 15,
    })
    result = analyze_pay_equity(df)
    assert result.available is False
    assert result.columns_detected["job_level"] is False
    assert result.columns_detected["department"] is False
    assert "comparability" in result.reason.lower()


def test_succession_fixture_lacks_salary_and_is_honestly_unavailable():
    # succession_test_data.csv has JobLevel + Nationality but no salary
    # column at all — must not fabricate a pay comparison.
    df = pd.read_csv(_ROOT / "succession_test_data.csv")
    result = analyze_pay_equity(df)
    assert result.available is False
    assert result.columns_detected["salary_or_compensation"] is False


def test_unavailable_result_carries_disclaimer_and_no_fabricated_numbers():
    result = unavailable_pay_equity_result("no data")
    assert result.pay_equity_confidence == PAY_EQUITY_CONFIDENCE
    assert result.n_comparisons_computed == 0
    assert result.comparisons == []
    assert len(result.disclaimer_en) > 20


# ── 5. Department-fallback-to-job-level on real, evenly-spread data ────────

def test_realistic_fixture_falls_back_to_job_level_when_department_too_fragmented(realistic_result):
    # 400 rows across 5 departments x 5 job levels x 2 genders means every
    # department x job-level x gender cell is well under 20 — every
    # comparison must fall back to job-level-only, not a fragmented
    # job-level+department cohort that was never actually usable.
    assert all(c.comparability_basis == "job_level" for c in realistic_result.comparisons)


def test_department_only_comparability_works_without_job_level():
    # Department alone (no JobLevel at all) must still be a valid
    # comparability factor per the spec ("JobLevel and/or Department").
    n = 30
    df = pd.DataFrame({
        "MonthlyIncome": [12_000] * n + [9_000] * n,
        "Gender": ["Male"] * n + ["Female"] * n,
        "Department": ["Sales"] * (2 * n),
    })
    result = analyze_pay_equity(df)
    assert result.available is True
    assert result.comparability_factors_used == ["department"]
    assert result.n_comparisons_computed == 1
    assert result.comparisons[0].comparability_basis == "department"


# ── Honesty framing + serialization ─────────────────────────────────────────

def test_available_result_carries_mandatory_disclaimer(realistic_result):
    assert realistic_result.pay_equity_confidence == PAY_EQUITY_CONFIDENCE
    assert "not a legal pay-equity" in realistic_result.disclaimer_en.lower()
    assert "qualified hr and legal review" in realistic_result.disclaimer_en.lower()
    assert len(realistic_result.disclaimer_ar) > 20


def test_to_dict_is_json_safe_and_includes_honesty_fields(realistic_result):
    import json
    d = pay_equity_to_dict(realistic_result)
    json.dumps(d)  # must not raise
    assert d["pay_equity_confidence"] == PAY_EQUITY_CONFIDENCE
    assert "disclaimer_en" in d and "disclaimer_ar" in d
    assert isinstance(d["comparisons"], list)
    assert all("p_value" in c for c in d["comparisons"])
