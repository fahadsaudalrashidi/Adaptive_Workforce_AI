"""
Phase 8 — Succession Planning / Internal Mobility Readiness engine tests.

Covers the required scenarios, each with real computed-value assertions
(not smoke-only tests):
  1. Datasets WITHOUT both a performance-rating and a tenure column — the
     real in-repo nitaqat_test_data.csv and messy_recruitment_data.csv
     fixtures — must return available=False with no fabricated score,
     listing what would activate the feature.
  2. A hand-computed synthetic dataset — readiness scores are independently
     reimplemented (not by calling the engine's own helpers) and compared
     exactly against the engine's output.
  3. Real data (test_employee_data.csv) — the aggregate readiness figures
     are independently recomputed and compared exactly.
  4. succession_test_data.csv — a purpose-built messy fixture with 5
     employees engineered to be "stuck high performers" (JobLevel=2, top
     performance, long tenure) of which exactly 4 clear the top-quartile
     tenure-within-peer-group threshold (the 5th sits at the 66.7th
     percentile of its 12-member peer group, below the 75th-percentile
     cutoff — a deterministic boundary case), and 5 employees engineered
     for the "high readiness + low promotion-fairness" combination.
  5. Department normalizer reuse, pipeline-level dedup reuse, missing-value
     exclusion (not guessing), and the mandatory honesty framing
     (is_validated_instrument=False, bilingual disclaimers) that must never
     be silently omittable.

Run: py -m pytest tests/test_succession_readiness_engine.py -v
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pandas as pd
import pytest

from backend.core.secure_file_ingestion import SecureFileIngestion
from backend.core.succession_readiness_engine import (
    READINESS_CALCULATION_CONFIDENCE,
    READINESS_TIER_THRESHOLDS,
    TENURE_WINDOW_YEARS,
    analyze_succession_readiness,
    succession_readiness_to_dict,
    unavailable_succession_result,
)

_ROOT = Path(__file__).resolve().parent.parent
_SUCCESSION_FIXTURE = _ROOT / "succession_test_data.csv"


def _hashed_id(raw_id: str) -> str:
    """Same one-way-hash scheme as _make_record_id() in the engine, used
    here to independently derive the expected record_id_safe for specific
    known EmployeeID values in the fixture."""
    h = hashlib.sha256(raw_id.encode()).hexdigest()[:6].upper()
    return f"EMP-{h}"


def _expected_readiness_scores(perf_ratings: list[float], tenures: list[float]) -> list[float]:
    """Independent reimplementation of the readiness formula documented in
    the module docstring — NOT calling the engine's own helper functions —
    for hand-verifiable assertions."""
    lo, hi = min(perf_ratings), max(perf_ratings)
    scores = []
    for p, t in zip(perf_ratings, tenures):
        pct = 50.0 if hi == lo else round((p - lo) / (hi - lo) * 100.0, 1)
        tenure_factor = min(1.0, t / TENURE_WINDOW_YEARS)
        scores.append(round(pct * tenure_factor, 1))
    return scores


# ── 1. No performance/tenure columns — must never fabricate a score ────────

def test_nitaqat_fixture_has_no_performance_or_tenure_columns_and_is_unavailable():
    df = pd.read_csv(_ROOT / "nitaqat_test_data.csv")
    result = analyze_succession_readiness(df)
    assert result.available is False
    assert result.n_total == 0
    assert result.avg_readiness_score is None
    assert result.top_candidates == []
    assert "performance" in result.reason.lower() or "tenure" in result.reason.lower()


def test_messy_recruitment_fixture_also_has_no_performance_or_tenure_columns():
    df = pd.read_csv(_ROOT / "messy_recruitment_data.csv")
    result = analyze_succession_readiness(df)
    assert result.available is False
    assert result.department_breakdown == []


def test_unavailable_reason_lists_activating_columns():
    df = pd.DataFrame({"EmployeeID": ["E1", "E2"], "Department": ["Sales", "Finance"]})
    result = analyze_succession_readiness(df)
    assert result.columns_detected["performance_rating"] is False
    assert result.columns_detected["tenure_years"] is False


def test_unavailable_when_only_one_of_two_required_columns_present():
    df = pd.DataFrame({"PerformanceRating": [4, 3, 2]})
    result = analyze_succession_readiness(df)
    assert result.available is False
    assert result.columns_detected["performance_rating"] is True
    assert result.columns_detected["tenure_years"] is False


def test_unavailable_on_empty_dataframe():
    result = analyze_succession_readiness(pd.DataFrame())
    assert result.available is False


def test_unavailable_result_has_no_fabricated_numbers():
    result = unavailable_succession_result("test reason")
    assert result.avg_readiness_score is None
    assert result.n_total == 0
    assert result.top_candidates == []
    assert result.department_breakdown == []


# ── 2. Hand-computed synthetic dataset — exact formula verification ────────

def test_readiness_scores_match_independent_hand_computation():
    perf = [1, 2, 3, 4]
    tenure = [0.5, 1.0, 2.0, 4.0]
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3", "E4"],
        "PerformanceRating": perf,
        "YearsAtCompany": tenure,
    })
    result = analyze_succession_readiness(df)
    assert result.available is True
    assert result.n_total == 4

    expected_scores = _expected_readiness_scores(perf, tenure)
    for t, exp in zip(tenure, expected_scores):
        match = [c for c in result.top_candidates if abs(c.tenure_years - t) < 1e-9]
        assert len(match) == 1, f"expected exactly one candidate with tenure {t}"
        assert match[0].readiness_score == pytest.approx(exp)

    expected_avg = round(sum(expected_scores) / len(expected_scores), 1)
    assert result.avg_readiness_score == pytest.approx(expected_avg)


@pytest.mark.parametrize("perf,tenure,expected_score,expected_tier", [
    (4, 4.0, 100.0, "High Readiness"),     # top perf, full tenure credit -> saturates at 100
    (4, 1.0, 50.0, "Emerging Readiness"),  # top perf, half tenure credit -> exactly 50
    (1, 0.5, 0.0, "Developing"),           # bottom perf -> 0 regardless of tenure
])
def test_single_candidate_tier_boundaries(perf, tenure, expected_score, expected_tier):
    """Two-employee dataset (min != max needed for a non-degenerate
    percentile) isolating one candidate's score/tier against the documented
    thresholds (High >= 70, Emerging >= 40, else Developing)."""
    df = pd.DataFrame({
        "EmployeeID": ["TARGET", "OTHER"],
        "PerformanceRating": [perf, 1 if perf != 1 else 4],
        "YearsAtCompany": [tenure, 5.0],
    })
    result = analyze_succession_readiness(df)
    target = [c for c in result.top_candidates if c.tenure_years == pytest.approx(tenure)][0]
    assert target.readiness_score == pytest.approx(expected_score)
    assert target.readiness_tier == expected_tier


def test_readiness_tier_thresholds_are_the_documented_values():
    assert READINESS_TIER_THRESHOLDS == {
        "High Readiness": 70.0, "Emerging Readiness": 40.0, "Developing": 0.0,
    }


def test_constant_performance_series_returns_neutral_percentile_not_divide_by_zero():
    """When every employee has the identical rating, there is no signal to
    differentiate on -- the engine must return the neutral midpoint (50.0)
    rather than dividing by zero or crashing."""
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3"],
        "PerformanceRating": [3, 3, 3],
        "YearsAtCompany": [5.0, 5.0, 5.0],
    })
    result = analyze_succession_readiness(df)
    assert result.available is True
    for c in result.top_candidates:
        assert c.performance_percentile == pytest.approx(50.0)


def test_missing_performance_or_tenure_values_excluded_not_guessed():
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3", "E4", "E5"],
        "PerformanceRating": [4, None, 3, 2, 1],
        "YearsAtCompany": [5.0, 3.0, None, 2.0, 1.0],
    })
    result = analyze_succession_readiness(df)
    # E2 (missing perf) and E3 (missing tenure) excluded -> 3 usable rows
    assert result.n_total == 3


# ── 3. Real data (test_employee_data.csv) — independently recomputed ───────

def test_real_employee_fixture_aggregate_matches_independent_recomputation():
    df = pd.read_csv(_ROOT / "test_employee_data.csv")
    result = analyze_succession_readiness(df)
    assert result.available is True

    valid = df.dropna(subset=["PerformanceRating", "YearsAtCompany"])
    valid = valid[valid["YearsAtCompany"] >= 0]
    expected_scores = _expected_readiness_scores(
        valid["PerformanceRating"].tolist(), valid["YearsAtCompany"].tolist(),
    )
    expected_n_high = sum(1 for s in expected_scores if s >= 70.0)
    expected_avg = round(sum(expected_scores) / len(expected_scores), 1)

    assert result.n_total == len(valid)
    assert result.n_high_readiness == expected_n_high
    assert result.avg_readiness_score == pytest.approx(expected_avg)


# ── 4. succession_test_data.csv — stuck-performer + low-fairness fixture ───

@pytest.fixture(scope="module")
def succession_df() -> pd.DataFrame:
    assert _SUCCESSION_FIXTURE.exists(), f"expected fixture at {_SUCCESSION_FIXTURE}"
    return pd.read_csv(_SUCCESSION_FIXTURE)


def test_fixture_columns_detected(succession_df):
    result = analyze_succession_readiness(succession_df)
    assert result.available is True
    assert result.columns_detected == {
        "performance_rating": True,
        "tenure_years": True,
        "job_level": True,
        "promotion_fairness": True,
        "department_or_sector": True,
    }


def test_stuck_high_performer_signal_fires_for_exactly_four_of_five_engineered_rows(succession_df):
    """Rows EMP013-EMP017 are a 5-member JobLevel=2 cohort engineered with
    top performance and long tenure (7.3-8.4 years) against 7 short-tenured
    peers (0.7-3.9 years) in the same 12-member JobLevel=2 group. EMP013's
    tenure (7.3) is the LOWEST of the five and lands at rank 8/12 = 66.7th
    percentile within the peer group -- below the 75th-percentile cutoff --
    so it must NOT be flagged, while the other four (75th-100th percentile)
    must be flagged. This is a deterministic boundary case, not a guess."""
    result = analyze_succession_readiness(succession_df)
    assert result.n_stuck_high_performers == 4

    stuck_ids = {c.record_id_safe for c in result.top_candidates if c.is_stuck_high_performer}
    assert _hashed_id("EMP014") in stuck_ids
    assert _hashed_id("EMP015") in stuck_ids
    assert _hashed_id("EMP016") in stuck_ids
    assert _hashed_id("EMP017") in stuck_ids

    not_stuck = [c for c in result.top_candidates if c.record_id_safe == _hashed_id("EMP013")]
    assert len(not_stuck) == 1
    assert not_stuck[0].is_stuck_high_performer is False


def test_high_readiness_low_fairness_combination_fires_for_all_five_engineered_rows(succession_df):
    """Rows EMP037-EMP041 are engineered with top performance, tenure >=
    TENURE_WINDOW_YEARS (full readiness credit -> readiness_score >= 70),
    and PromotionFairness=1 (bottom of the fixture's 1-5 range -> low
    fairness percentile). All five must be flagged for the specific
    actionable combination."""
    result = analyze_succession_readiness(succession_df)
    assert result.n_high_readiness_low_fairness == 5

    expected_ids = {_hashed_id(f"EMP{i:03d}") for i in range(37, 42)}
    flagged_ids = {
        c.record_id_safe for c in result.top_candidates
        if c.high_readiness_low_fairness_flag
    }
    assert expected_ids <= flagged_ids
    for c in result.top_candidates:
        if c.record_id_safe in expected_ids:
            assert c.readiness_score >= READINESS_TIER_THRESHOLDS["High Readiness"]


def test_fixture_department_names_reuse_department_normalizer(succession_df):
    result = analyze_succession_readiness(succession_df)
    assert len(result.department_normalization_notes) >= 2
    depts = {d.department for d in result.department_breakdown}
    assert "Sales" in depts or "Finance" in depts or "Operations" in depts
    # Raw un-normalized variants must never leak through as their own group.
    assert "finance" not in depts
    assert "Operations " not in depts
    assert "مبيعات" not in depts


def test_duplicate_row_removed_by_pipeline_level_dedup(succession_df):
    """The fixture contains one exact duplicate EmployeeID row. Succession
    readiness flows through the same SecureFileIngestion.scan() pipeline as
    every other module — the duplicate is removed before
    analyze_succession_readiness() ever sees it, so this confirms reuse
    rather than a second, independent dedup implementation in this module."""
    buf = io.BytesIO()
    succession_df.to_csv(buf, index=False, encoding="utf-8-sig")
    raw = buf.getvalue()

    scanner = SecureFileIngestion()
    report = scanner.scan(raw, "succession_dup.csv", "tenant-a")
    assert report.ingestion_result.row_count == len(succession_df) - 1
    assert any("duplicate row" in w for w in report.warnings)


# ── 5. Mandatory honesty framing — never silently omittable ────────────────

def test_available_result_always_carries_heuristic_disclaimer(succession_df):
    result = analyze_succession_readiness(succession_df)
    assert result.is_validated_instrument is False
    assert result.calculation_confidence == READINESS_CALCULATION_CONFIDENCE
    assert "constructed heuristic" in result.disclaimer_en.lower()
    assert len(result.disclaimer_ar) > 20
    assert "constructed heuristic" in result.narrative_en.lower() or \
        "heuristic" in result.narrative_en.lower()


def test_unavailable_result_also_carries_disclaimer_fields():
    result = unavailable_succession_result("no data")
    assert result.is_validated_instrument is False
    assert result.calculation_confidence == READINESS_CALCULATION_CONFIDENCE
    assert len(result.disclaimer_en) > 20
    assert len(result.disclaimer_ar) > 20


def test_formula_description_documents_the_actual_formula():
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2"],
        "PerformanceRating": [4, 1],
        "YearsAtCompany": [3.0, 0.5],
    })
    result = analyze_succession_readiness(df)
    assert "performance_percentile" in result.formula_description_en
    assert "tenure_factor" in result.formula_description_en
    assert len(result.formula_description_ar) > 20


# ── Serialization ────────────────────────────────────────────────────────────

def test_to_dict_is_json_safe_and_includes_honesty_fields(succession_df):
    import json
    result = analyze_succession_readiness(succession_df)
    d = succession_readiness_to_dict(result)
    json.dumps(d)  # must not raise
    assert d["is_validated_instrument"] is False
    assert "calculation_confidence" in d
    assert "disclaimer_en" in d and "disclaimer_ar" in d
    assert isinstance(d["top_candidates"], list)
    assert isinstance(d["department_breakdown"], list)


def test_to_dict_unavailable_is_json_safe():
    import json
    result = unavailable_succession_result("no data")
    d = succession_readiness_to_dict(result)
    json.dumps(d)
    assert d["available"] is False
    assert d["avg_readiness_score"] is None


# ── Phase 8 Part 2: high_readiness_record_ids (Nitaqat cross-link support) ──

def test_high_readiness_record_ids_covers_full_count_not_just_top_20(succession_df):
    """top_candidates is capped at the top 20 by score for display, but a
    Nitaqat cross-link ('N high-readiness Saudi employees') needs every
    high-readiness employee's ID, not just the display slice."""
    result = analyze_succession_readiness(succession_df)
    assert len(result.high_readiness_record_ids) == result.n_high_readiness
    assert len(set(result.high_readiness_record_ids)) == len(result.high_readiness_record_ids)


def test_high_readiness_record_ids_match_the_engineered_low_fairness_rows(succession_df):
    """EMP037-EMP041 were engineered with readiness_score >= 70 (High
    Readiness tier) -- their hashed IDs must appear in the full
    high-readiness ID list, confirming it isn't silently truncated."""
    result = analyze_succession_readiness(succession_df)
    for i in range(37, 42):
        assert _hashed_id(f"EMP{i:03d}") in result.high_readiness_record_ids


def test_unavailable_result_has_empty_high_readiness_record_ids():
    result = unavailable_succession_result("no data")
    assert result.high_readiness_record_ids == []
