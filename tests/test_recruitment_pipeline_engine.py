"""
Phase 5 — Recruitment Pipeline Status Tracker tests.

Covers three required scenarios, each with real computed-value assertions
(not smoke-only tests):
  1. A dataset WITHOUT recruitment columns (the real in-repo
     test_employee_data.csv fixture — genuine structured HR employee data
     with zero candidate/hiring columns) — must return available=False with
     no fabricated funnel, listing what would activate the feature.
  2. A dataset WITH recruitment columns — funnel counts, conversion rates,
     and time-to-hire are independently recomputed by hand in the test and
     compared exactly against the engine's output.
  3. A messy dataset — mixed Arabic/English pipeline-stage names, an
     invalid hire-before-application date sequence, and a duplicate
     candidate row — confirming the engine reuses department_normalizer.py
     and the pipeline-level dedup already proven in
     PHASE_4_CORRECTIONS_REPORT.md, rather than needing new bug-prone logic.

Run: py -m pytest tests/test_recruitment_pipeline_engine.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.financial_intelligence_engine import SECTOR_BENCHMARK_CONFIDENCE
from backend.core.recruitment_pipeline_engine import (
    analyze_recruitment_pipeline,
    recruitment_pipeline_to_dict,
    unavailable_recruitment_result,
)
from backend.core.secure_file_ingestion import SecureFileIngestion

_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "test_employee_data.csv"


# ── 1. No recruitment columns — must never fabricate a funnel ──────────────

def test_real_employee_fixture_has_no_recruitment_columns_and_is_unavailable():
    """test_employee_data.csv is genuine structured HR employee data with no
    candidate/hiring columns — this is the expected, real-world case this
    module must handle honestly."""
    df = pd.read_csv(_FIXTURE_PATH)
    result = analyze_recruitment_pipeline(df)
    assert result.available is False
    assert result.n_candidates_total == 0
    assert result.current_stage_distribution == []
    assert result.avg_time_to_hire_days is None
    assert "stage" in result.reason.lower() or "Stage" in result.reason


def test_unavailable_reason_lists_columns_that_would_activate_feature():
    df = pd.DataFrame({"EmployeeID": ["E1", "E2"], "Department": ["Sales", "Finance"]})
    result = analyze_recruitment_pipeline(df)
    assert result.available is False
    assert "candidate" in result.reason.lower() or "stage" in result.reason.lower()
    assert result.columns_detected["stage"] is False
    assert result.columns_detected["candidate_id"] is False


def test_unavailable_on_empty_dataframe():
    result = analyze_recruitment_pipeline(pd.DataFrame())
    assert result.available is False
    assert result.n_candidates_total == 0


def test_unavailable_result_has_no_fabricated_numbers():
    result = unavailable_recruitment_result("test reason")
    assert result.n_candidates_total == 0
    assert result.avg_time_to_hire_days is None
    assert result.cost_per_hire_sar is None
    assert result.current_stage_distribution == []


# ── 2. Real recruitment data — hand-recomputed funnel/conversion/time-to-hire ──

@pytest.fixture
def recruitment_df() -> pd.DataFrame:
    """20 candidates: 4 Hired, 4 Rejected, rest spread across the funnel.
    Ladder: Applied(20) -> Screening(15) -> Interview(10) -> Offer(6) -> Hired(4).
    Exactly mirrors a manually-designed funnel so expected values are exact."""
    n = 20
    stages = ["Interview"] * n  # placeholder, overwritten below
    df = pd.DataFrame({
        "CandidateID": [f"C{i:03d}" for i in range(1, n + 1)],
        "Stage": stages,
        "Department": ["Sales"] * 10 + ["Engineering"] * 10,
        "Source": ["Referral"] * 5 + ["LinkedIn"] * 5 + ["Job Board"] * 5 + ["Agency"] * 5,
        "ApplicationDate": pd.date_range("2025-01-01", periods=n, freq="D"),
    })
    df["Stage"] = "Screening"          # baseline: reached at least Screening
    df.loc[0:14, "Stage"] = "Screening"  # rows 0-14 (15 rows) at least Screening
    df.loc[0:9, "Stage"] = "Interview"   # rows 0-9 (10 rows) at least Interview
    df.loc[0:5, "Stage"] = "Offer"       # rows 0-5 (6 rows) at least Offer
    df.loc[0:3, "Stage"] = "Hired"       # rows 0-3 (4 rows) Hired
    df.loc[15, "Stage"] = "Applied"      # row 15: only Applied (not even Screening)
    df.loc[16:19, "Stage"] = "Rejected"  # rows 16-19 (4 rows) Rejected
    df["HireDate"] = pd.NaT
    df.loc[0:3, "HireDate"] = df.loc[0:3, "ApplicationDate"] + pd.Timedelta(days=20)
    return df


def test_funnel_counts_match_hand_computation(recruitment_df):
    result = analyze_recruitment_pipeline(recruitment_df)
    assert result.available is True
    assert result.n_candidates_total == 20
    counts = {s.stage: s.n_candidates for s in result.current_stage_distribution}
    # Applied floor = everyone (20), including Rejected — see module docstring.
    assert counts == {"Applied": 20, "Screening": 15, "Interview": 10, "Offer": 6, "Hired": 4}


def test_conversion_rates_match_hand_computation(recruitment_df):
    result = analyze_recruitment_pipeline(recruitment_df)
    conv = {s.stage: s.conversion_from_previous_pct for s in result.current_stage_distribution}
    assert conv["Applied"] is None
    assert conv["Screening"] == pytest.approx(round(100.0 * 15 / 20, 1))
    assert conv["Interview"] == pytest.approx(round(100.0 * 10 / 15, 1))
    assert conv["Offer"] == pytest.approx(round(100.0 * 6 / 10, 1))
    assert conv["Hired"] == pytest.approx(round(100.0 * 4 / 6, 1))


def test_biggest_dropoff_stage_is_the_lowest_conversion(recruitment_df):
    result = analyze_recruitment_pipeline(recruitment_df)
    # Offer conversion (60%) is lower than Screening (75%), Interview (66.7%), Hired (66.7%).
    assert result.biggest_dropoff_stage == "Offer"


def test_rejection_count_and_rate(recruitment_df):
    result = analyze_recruitment_pipeline(recruitment_df)
    assert result.n_rejected == 4
    assert result.rejection_rate_pct == pytest.approx(20.0)


def test_time_to_hire_matches_hand_computation(recruitment_df):
    """4 hired candidates, each with HireDate = ApplicationDate + 20 days exactly."""
    result = analyze_recruitment_pipeline(recruitment_df)
    assert result.n_time_to_hire_computed == 4
    assert result.avg_time_to_hire_days == pytest.approx(20.0)


def test_department_breakdown_hire_rate(recruitment_df):
    result = analyze_recruitment_pipeline(recruitment_df)
    by_dept = {d.department: d for d in result.department_breakdown}
    # All 4 hires are in rows 0-3, which are all "Sales" (first 10 rows).
    assert by_dept["Sales"].n_candidates == 10
    assert by_dept["Sales"].n_hired == 4
    assert by_dept["Sales"].hire_rate_pct == pytest.approx(40.0)
    assert by_dept["Engineering"].n_candidates == 10
    assert by_dept["Engineering"].n_hired == 0
    assert by_dept["Engineering"].hire_rate_pct == pytest.approx(0.0)


def test_source_breakdown_hire_rate(recruitment_df):
    result = analyze_recruitment_pipeline(recruitment_df)
    by_source = {s.source: s for s in result.source_breakdown}
    # Rows 0-3 (all hired) are within the first 5 rows -> "Referral".
    assert by_source["Referral"].n_candidates == 5
    assert by_source["Referral"].n_hired == 4
    assert by_source["LinkedIn"].n_hired == 0


def test_to_dict_is_json_safe_and_complete(recruitment_df):
    result = analyze_recruitment_pipeline(recruitment_df)
    d = recruitment_pipeline_to_dict(result)
    assert d["available"] is True
    assert isinstance(d["current_stage_distribution"], list) and len(d["current_stage_distribution"]) == 5
    assert isinstance(d["department_breakdown"], list)
    assert isinstance(d["source_breakdown"], list)
    assert "avg_time_to_hire_days" in d


# ── 3. Messy data — reuses department_normalizer.py, no new bug-prone logic ──

def test_messy_mixed_language_stage_names_merge_correctly():
    """"Interview"/"مقابلة" and "Hired"/"hired" must be recognised as the
    same pipeline stage — the exact live-testing bug pattern already fixed
    for department names, reproduced here for pipeline stages."""
    df = pd.DataFrame({
        "CandidateID": ["C1", "C2", "C3", "C4"],
        "Stage": ["Interview", "مقابلة", "Hired", "hired"],
        "ApplicationDate": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
    })
    result = analyze_recruitment_pipeline(df)
    assert result.available is True
    counts = {s.stage: s.n_candidates for s in result.current_stage_distribution}
    assert counts["Interview"] == 4   # all 4 reached at least Interview
    assert counts["Hired"] == 2       # only the 2 Hired/hired rows
    assert len(result.stage_normalization_notes) == 2
    assert any("Interview" in n for n in result.stage_normalization_notes)
    assert any("Hired" in n for n in result.stage_normalization_notes)


def test_messy_department_names_reuse_department_normalizer():
    """"Sales"/"مبيعات" and "Finance"/"finance" — same fix as HR data,
    reused verbatim via department_normalizer.py."""
    df = pd.DataFrame({
        "CandidateID": ["C1", "C2", "C3", "C4"],
        "Stage": ["Applied", "Applied", "Applied", "Applied"],
        "Department": ["Sales", "مبيعات", "Finance", "finance"],
        "ApplicationDate": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
    })
    result = analyze_recruitment_pipeline(df)
    by_dept = {d.department: d.n_candidates for d in result.department_breakdown}
    assert by_dept == {"Sales": 2, "Finance": 2}
    assert any("Sales" in n for n in result.department_normalization_notes)
    assert any("Finance" in n for n in result.department_normalization_notes)


def test_invalid_hire_before_application_date_excluded_with_warning():
    """A hire date before the application date is an impossible sequence —
    must be excluded from the average, never silently produce a negative
    duration, and must surface a visible data-quality warning."""
    df = pd.DataFrame({
        "CandidateID": ["C1", "C2", "C3"],
        "Stage": ["Hired", "Hired", "Hired"],
        "ApplicationDate": ["2025-01-10", "2025-01-10", "2025-01-10"],
        "HireDate": ["2025-01-30", "2024-12-01", "2025-01-25"],  # C2 is impossible
    })
    result = analyze_recruitment_pipeline(df)
    assert result.invalid_date_sequences_excluded == 1
    assert result.n_time_to_hire_computed == 2
    assert any("impossible" in w.lower() for w in result.date_quality_warnings)
    # No negative duration ever leaks into the average.
    assert result.avg_time_to_hire_days is not None
    assert result.avg_time_to_hire_days > 0


def test_missing_stage_value_does_not_crash_and_is_bucketed():
    """A None/NaN stage value must not crash (same NaN-safety discipline as
    department_normalizer.py's fix) and must not be silently dropped."""
    import numpy as np
    df = pd.DataFrame({
        "CandidateID": ["C1", "C2", "C3"],
        "Stage": ["Applied", None, np.nan],
        "ApplicationDate": ["2025-01-01", "2025-01-02", "2025-01-03"],
    })
    result = analyze_recruitment_pipeline(df)  # must not raise
    assert result.available is True
    assert result.n_candidates_total == 3


def test_duplicate_candidate_row_is_removed_by_pipeline_level_dedup():
    """Recruitment data flows through the same SecureFileIngestion.scan()
    pipeline as every other module — a duplicate candidate row is removed
    before analyze_recruitment_pipeline() ever sees it (see
    PHASE_4_CORRECTIONS_REPORT.md §2). This confirms the reuse, rather than
    needing a second, independent dedup implementation in this module."""
    import io

    df = pd.DataFrame({
        "CandidateID": ["C001", "C001", "C002", "C003"],
        "Stage": ["Interview", "Interview", "Hired", "Applied"],
        "ApplicationDate": ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-03"],
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    raw = buf.getvalue()

    scanner = SecureFileIngestion()
    report = scanner.scan(raw, "recruitment_dup.csv", "tenant-a")
    assert report.ingestion_result.row_count == 3   # deduped from 4 to 3
    assert any("duplicate row" in w for w in report.warnings)

    result = analyze_recruitment_pipeline(report.ingestion_result.df)
    assert result.n_candidates_total == 3  # not 4 — dedup already happened upstream


# ── Rejection-reason theme reuse (exit_interview_intelligence_engine.py) ────

def test_rejection_reason_themes_reuse_exit_interview_engine():
    reasons = [
        "Salary expectations too high for this role",
        "Salary expectations were too high",
        "The offered salary was too low for the role",
        "Not enough relevant experience",
        "Lacks required experience for this position",
    ]
    df = pd.DataFrame({
        "CandidateID": [f"C{i}" for i in range(len(reasons))],
        "Stage": ["Rejected"] * len(reasons),
        "ApplicationDate": pd.date_range("2025-01-01", periods=len(reasons)),
        "RejectionReason": reasons,
    })
    result = analyze_recruitment_pipeline(df)
    assert result.rejection_reason_themes is not None
    assert result.rejection_reason_themes["available"] is True
    assert result.rejection_reason_themes["n_responses_analyzed"] == len(reasons)


def test_rejection_reason_themes_none_when_too_few_responses():
    df = pd.DataFrame({
        "CandidateID": ["C1", "C2"],
        "Stage": ["Rejected", "Rejected"],
        "ApplicationDate": ["2025-01-01", "2025-01-02"],
        "RejectionReason": ["Too expensive", "Not a fit"],
    })
    result = analyze_recruitment_pipeline(df)
    assert result.rejection_reason_themes is None


# ── Cost per hire — never a new formula ─────────────────────────────────────

def test_cost_per_hire_observed_when_real_cost_column_present():
    df = pd.DataFrame({
        "CandidateID": ["C1", "C2"],
        "Stage": ["Hired", "Hired"],
        "ApplicationDate": ["2025-01-01", "2025-01-02"],
        "RecruitmentCost": [15000.0, 17000.0],
    })
    result = analyze_recruitment_pipeline(df)
    assert result.cost_per_hire_confidence == "observed"
    assert result.cost_per_hire_sar == pytest.approx(16000.0)


def test_cost_per_hire_uncalibrated_when_no_cost_column():
    df = pd.DataFrame({
        "CandidateID": ["C1"],
        "Stage": ["Hired"],
        "ApplicationDate": ["2025-01-01"],
    })
    result = analyze_recruitment_pipeline(df)
    assert result.cost_per_hire_confidence == SECTOR_BENCHMARK_CONFIDENCE
    assert result.cost_per_hire_sar is not None and result.cost_per_hire_sar > 0


def test_cost_per_hire_none_when_no_one_hired():
    df = pd.DataFrame({
        "CandidateID": ["C1", "C2"],
        "Stage": ["Applied", "Screening"],
        "ApplicationDate": ["2025-01-01", "2025-01-02"],
    })
    result = analyze_recruitment_pipeline(df)
    assert result.cost_per_hire_sar is None
    assert result.cost_per_hire_confidence is None
