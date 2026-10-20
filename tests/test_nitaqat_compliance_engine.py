"""
Phase 7 — Nitaqat / Saudization Compliance engine tests.

Covers three required scenarios, each with real computed-value assertions
(not smoke-only tests):
  1. A dataset WITHOUT a nationality/Saudi-status column — the real in-repo
     test_employee_data.csv and messy_test_data.csv fixtures — must return
     available=False with no fabricated percentage, listing what would
     activate the feature.
  2. A dataset WITH a nationality column — Saudization percentages and band
     assignments are independently hand-computed and compared exactly
     against the engine's output, across all 5 illustrative bands plus the
     small-establishment two-tier rule.
  3. Messy data (nitaqat_test_data.csv) — mixed Arabic/English nationality
     tokens, inconsistent casing, missing values, a duplicate row, and mixed
     department casing — confirming the engine reuses department_normalizer.py
     and the pipeline-level dedup already proven in
     PHASE_4_CORRECTIONS_REPORT.md, rather than needing new bug-prone logic.

Also covers the mandatory non-negotiable honesty framing: every
available=True result must carry is_official_calculation=False and a
non-empty illustrative-estimate disclaimer, and this must never be silently
omittable.

Run: py -m pytest tests/test_nitaqat_compliance_engine.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.nitaqat_compliance_engine import (
    ILLUSTRATIVE_BAND_THRESHOLDS,
    NITAQAT_CALCULATION_CONFIDENCE,
    SMALL_ESTABLISHMENT_MAX_HEADCOUNT,
    analyze_nitaqat_compliance,
    get_saudi_status_by_record_id,
    nitaqat_compliance_to_dict,
    unavailable_nitaqat_result,
)
from backend.core.secure_file_ingestion import SecureFileIngestion

_ROOT = Path(__file__).resolve().parent.parent
_NITAQAT_FIXTURE = _ROOT / "nitaqat_test_data.csv"
_SUCCESSION_FIXTURE = _ROOT / "succession_test_data.csv"
_REALISTIC_MULTIDEPT_FIXTURE = _ROOT / "nitaqat_realistic_multidept_test_data.csv"


# ── 1. No nationality column — must never fabricate a percentage ───────────

def test_real_employee_fixture_has_no_nationality_column_and_is_unavailable():
    df = pd.read_csv(_ROOT / "test_employee_data.csv")
    result = analyze_nitaqat_compliance(df)
    assert result.available is False
    assert result.n_total == 0
    assert result.saudization_pct is None
    assert result.band is None
    assert "nationality" in result.reason.lower() or "saudi" in result.reason.lower()


def test_messy_test_data_fixture_also_has_no_nationality_column():
    df = pd.read_csv(_ROOT / "messy_test_data.csv")
    result = analyze_nitaqat_compliance(df)
    assert result.available is False
    assert result.department_breakdown == []


def test_unavailable_reason_lists_activating_columns():
    df = pd.DataFrame({"EmployeeID": ["E1", "E2"], "Department": ["Sales", "Finance"]})
    result = analyze_nitaqat_compliance(df)
    assert result.columns_detected["nationality_or_saudi_status"] is False


def test_unavailable_on_empty_dataframe():
    result = analyze_nitaqat_compliance(pd.DataFrame())
    assert result.available is False


def test_unavailable_result_has_no_fabricated_numbers():
    result = unavailable_nitaqat_result("test reason")
    assert result.saudization_pct is None
    assert result.band is None
    assert result.n_total == 0
    assert result.department_breakdown == []


# ── 2. Real nationality data — hand-verified band assignment across all 5 bands ──
# Thresholds recalibrated 2026-08-07 (Platinum >=75 / High Green >=60 /
# Mid Green >=40 / Low Green >=20 / Red >=0) after live testing found the
# original 40/30/20/10 spacing flattened every realistic 40-100% department
# into "Platinum". See nitaqat_compliance_engine.py's module docstring.

@pytest.mark.parametrize("n_saudi,n_total,expected_pct,expected_band", [
    (75, 100, 75.0, "Platinum"),     # exactly at the Platinum threshold
    (65, 100, 65.0, "High Green"),
    (45, 100, 45.0, "Mid Green"),
    (25, 100, 25.0, "Low Green"),
    (5, 100, 5.0, "Red"),
    (74, 100, 74.0, "High Green"),   # just below Platinum
])
def test_band_assignment_matches_hand_computation(n_saudi, n_total, expected_pct, expected_band):
    n_non_saudi = n_total - n_saudi
    df = pd.DataFrame({
        "Nationality": ["Saudi"] * n_saudi + ["India"] * n_non_saudi,
    })
    result = analyze_nitaqat_compliance(df)
    assert result.available is True
    assert result.n_saudi == n_saudi
    assert result.n_total == n_total
    assert result.saudization_pct == pytest.approx(expected_pct)
    assert result.band == expected_band


def test_band_thresholds_are_the_documented_illustrative_values():
    assert ILLUSTRATIVE_BAND_THRESHOLDS == {
        "Platinum": 75.0, "High Green": 60.0, "Mid Green": 40.0,
        "Low Green": 20.0, "Red": 0.0,
    }


def test_small_establishment_green_with_at_least_one_saudi():
    """Confirmed real structural rule (not illustrative): <=5 employees uses
    a simplified two-tier Green/Red system."""
    df = pd.DataFrame({"Nationality": ["Saudi", "India", "Egypt"]})
    result = analyze_nitaqat_compliance(df)
    assert result.n_total == 3
    assert result.n_total <= SMALL_ESTABLISHMENT_MAX_HEADCOUNT
    assert result.is_small_establishment is True
    assert result.band == "Green"


def test_small_establishment_red_with_zero_saudi():
    df = pd.DataFrame({"Nationality": ["India", "Egypt", "Pakistan"]})
    result = analyze_nitaqat_compliance(df)
    assert result.is_small_establishment is True
    assert result.band == "Red"


def test_missing_nationality_values_excluded_not_guessed():
    df = pd.DataFrame({
        "Nationality": ["Saudi", "Saudi", None, "", "India", "India", "India", "India"],
    })
    result = analyze_nitaqat_compliance(df)
    # 2 missing excluded from denominator; 2 Saudi / 6 classified = 33.3%
    assert result.n_excluded_missing == 2
    assert result.n_total == 6
    assert result.n_saudi == 2
    assert result.saudization_pct == pytest.approx(33.3, abs=0.1)


def test_bilingual_saudi_tokens_recognised():
    """"Saudi"/"سعودي"/"saudi"/"KSA" must all classify as Saudi; "Non-Saudi"/
    "غير سعودي" must classify as non-Saudi — same EN/AR consistency
    discipline as every other module this session."""
    df = pd.DataFrame({
        "Nationality": ["Saudi", "سعودي", "saudi", "KSA", "Non-Saudi", "غير سعودي", "India"],
    })
    result = analyze_nitaqat_compliance(df)
    assert result.n_saudi == 4
    assert result.n_non_saudi == 3
    assert result.n_total == 7


# ── 2b. Realistic multi-department dataset — band differentiation ──────────
# Regression coverage for the confirmed live-testing bug: the ORIGINAL
# 40/30/20/10 thresholds classified every department in a realistic
# 46.7%-75.0% range as "Platinum" (flat, useless for comparison). The
# recalibrated 75/60/40/20 thresholds must differentiate this exact shape
# of data into multiple bands.

@pytest.fixture(scope="module")
def realistic_multidept_df() -> pd.DataFrame:
    assert _REALISTIC_MULTIDEPT_FIXTURE.exists(), \
        f"expected fixture at {_REALISTIC_MULTIDEPT_FIXTURE}"
    return pd.read_csv(_REALISTIC_MULTIDEPT_FIXTURE)


def test_realistic_multidept_fixture_is_not_flat_platinum(realistic_multidept_df):
    """The exact bug: 9 departments spanning 46.7%-75.0% Saudization must
    NOT all collapse into a single band."""
    result = analyze_nitaqat_compliance(realistic_multidept_df)
    assert result.available is True
    assert len(result.department_breakdown) == 9

    pcts = sorted(d.saudization_pct for d in result.department_breakdown)
    assert pcts[0] == pytest.approx(46.7, abs=0.1)
    assert pcts[-1] == pytest.approx(75.0, abs=0.1)

    bands_used = {d.band for d in result.department_breakdown}
    assert len(bands_used) >= 3, (
        f"expected at least 3 distinct bands across a 46.7%-75.0% spread, got "
        f"only {bands_used} — thresholds are too coarse again"
    )


def test_realistic_multidept_fixture_band_assignments_match_new_thresholds(realistic_multidept_df):
    """Independently recompute the expected band for each department's exact
    percentage against the new threshold constants (not calling the
    engine's own _band_for_pct()) and assert an exact match."""
    result = analyze_nitaqat_compliance(realistic_multidept_df)

    def expected_band(pct: float) -> str:
        for band in ["Platinum", "High Green", "Mid Green", "Low Green"]:
            if pct >= ILLUSTRATIVE_BAND_THRESHOLDS[band]:
                return band
        return "Red"

    for d in result.department_breakdown:
        assert d.band == expected_band(d.saudization_pct), (
            f"{d.department} at {d.saudization_pct}% got band {d.band}, "
            f"expected {expected_band(d.saudization_pct)}"
        )

    # Specific hand-verified spot checks matching the fixture's known values.
    by_dept = {d.department: d for d in result.department_breakdown}
    assert by_dept["Procurement"].band == "Mid Green"       # 46.7%
    assert by_dept["Operations"].band == "Platinum"         # 75.0%
    assert by_dept["Sales"].band == "High Green"             # 70.0%


# ── 3. Messy data fixture — department normalizer reuse + pipeline dedup ────

@pytest.fixture(scope="module")
def nitaqat_df() -> pd.DataFrame:
    assert _NITAQAT_FIXTURE.exists(), f"expected fixture at {_NITAQAT_FIXTURE}"
    return pd.read_csv(_NITAQAT_FIXTURE)


def test_messy_fixture_department_names_reuse_department_normalizer(nitaqat_df):
    result = analyze_nitaqat_compliance(nitaqat_df)
    assert result.available is True
    assert len(result.department_normalization_notes) >= 2
    depts = {d.department for d in result.department_breakdown}
    # Merged canonical labels only — no raw "مبيعات"/"finance"/"Operations " leaking through.
    assert "Sales" in depts or "Finance" in depts or "Operations" in depts
    assert "مبيعات" not in depts
    assert "finance" not in depts
    assert "Operations " not in depts


def test_messy_fixture_saudization_pct_matches_independent_classification(nitaqat_df):
    """Independently reclassify every raw Nationality value (not calling the
    engine's own function) and assert the engine's aggregate matches exactly."""
    saudi_tokens = {
        "saudi", "saudi arabia", "ksa", "sa", "سعودي", "سعودية",
        "السعودية", "المملكة العربية السعودية",
    }
    expected_saudi = 0
    expected_total = 0
    for raw in nitaqat_df["Nationality"]:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)) or not str(raw).strip():
            continue
        expected_total += 1
        if str(raw).strip().lower() in saudi_tokens:
            expected_saudi += 1

    result = analyze_nitaqat_compliance(nitaqat_df)
    assert result.n_total == expected_total
    assert result.n_saudi == expected_saudi
    expected_pct = round(100.0 * expected_saudi / expected_total, 1)
    assert result.saudization_pct == pytest.approx(expected_pct)


def test_duplicate_row_removed_by_pipeline_level_dedup(nitaqat_df):
    """The fixture contains one exact duplicate EmployeeID row. Recruitment/
    HR data flows through the same SecureFileIngestion.scan() pipeline as
    every other module — the duplicate is removed before
    analyze_nitaqat_compliance() ever sees it (PHASE_4_CORRECTIONS_REPORT.md
    §2), so this confirms reuse rather than needing a second, independent
    dedup implementation in this module."""
    import io
    buf = io.BytesIO()
    nitaqat_df.to_csv(buf, index=False, encoding="utf-8-sig")
    raw = buf.getvalue()

    scanner = SecureFileIngestion()
    report = scanner.scan(raw, "nitaqat_dup.csv", "tenant-a")
    assert report.ingestion_result.row_count == len(nitaqat_df) - 1
    assert any("duplicate row" in w for w in report.warnings)

    result = analyze_nitaqat_compliance(report.ingestion_result.df)
    assert result.n_total + result.n_excluded_missing == len(nitaqat_df) - 1


# ── Mandatory honesty framing — never silently omittable ────────────────────

def test_available_result_always_carries_illustrative_disclaimer():
    df = pd.DataFrame({"Nationality": ["Saudi"] * 10 + ["India"] * 10})
    result = analyze_nitaqat_compliance(df)
    assert result.is_official_calculation is False
    assert result.calculation_confidence == NITAQAT_CALCULATION_CONFIDENCE
    assert "not an official" in result.disclaimer_en.lower() or "illustrative" in result.disclaimer_en.lower()
    assert len(result.disclaimer_ar) > 20
    assert "illustrative" in result.narrative_en.lower() or "not an official" in result.narrative_en.lower()


def test_unavailable_result_also_carries_disclaimer_fields():
    result = unavailable_nitaqat_result("no data")
    assert result.is_official_calculation is False
    assert result.calculation_confidence == NITAQAT_CALCULATION_CONFIDENCE
    assert len(result.disclaimer_en) > 20


# ── Phase 17 — Qiwa contract-authentication regulatory update ──────────────
# Effective 2026-04-15, real Nitaqat headcount also requires Qiwa contract
# authentication (see module docstring for sources) — this platform only
# ever sees nationality data, so every disclaimer must say so explicitly,
# additive to (not replacing) the pre-existing illustrative-estimate text.

def test_available_result_discloses_qiwa_contract_authentication_gap():
    df = pd.DataFrame({"Nationality": ["Saudi"] * 10 + ["India"] * 10})
    result = analyze_nitaqat_compliance(df)
    assert "qiwa" in result.disclaimer_en.lower()
    assert "contract authentication" in result.disclaimer_en.lower()
    assert "april 2026" in result.disclaimer_en.lower()
    # Additive, not a replacement — the original disclaimer text must survive.
    assert "not an official" in result.disclaimer_en.lower()
    assert "قوى" in result.disclaimer_ar
    assert "أبريل 2026" in result.disclaimer_ar


def test_unavailable_result_also_discloses_qiwa_contract_authentication_gap():
    result = unavailable_nitaqat_result("no data")
    assert "qiwa" in result.disclaimer_en.lower()
    assert "contract authentication" in result.disclaimer_en.lower()


# ── Serialization ────────────────────────────────────────────────────────────

def test_to_dict_is_json_safe_and_includes_honesty_fields(nitaqat_df):
    import json
    result = analyze_nitaqat_compliance(nitaqat_df)
    d = nitaqat_compliance_to_dict(result)
    json.dumps(d)  # must not raise
    assert d["is_official_calculation"] is False
    assert "calculation_confidence" in d
    assert "disclaimer_en" in d and "disclaimer_ar" in d
    assert isinstance(d["department_breakdown"], list)


# ── Phase 8 extension point: get_saudi_status_by_record_id() ───────────────
# Additive cross-link function for succession_readiness_engine.py — these
# tests confirm it in isolation, independent of the succession engine.

def test_saudi_status_map_none_when_no_id_column():
    """A positional fallback ID here would not reliably match another
    module's positional fallback (computed over a differently-filtered row
    subset) -- so the function must refuse (return None) rather than risk a
    silent wrong join, not silently key by row position."""
    df = pd.DataFrame({"Nationality": ["Saudi", "India"]})
    assert get_saudi_status_by_record_id(df) is None


def test_saudi_status_map_none_when_no_nationality_column():
    df = pd.DataFrame({"EmployeeID": ["E1", "E2"], "PerformanceRating": [4, 3]})
    assert get_saudi_status_by_record_id(df) is None


def test_saudi_status_map_none_on_empty_dataframe():
    assert get_saudi_status_by_record_id(pd.DataFrame()) is None


def test_saudi_status_map_uses_same_hash_scheme_as_succession_engine():
    """Independently reimplement the hash scheme (sha256, first 6 hex chars,
    uppercased, EMP- prefixed) and confirm the map's keys match exactly --
    this is the same scheme succession_readiness_engine.py's
    _make_record_id() uses for named-ID rows, which is what makes the join
    in local_analysis_routes.py's /succession-readiness route valid."""
    import hashlib
    df = pd.DataFrame({
        "EmployeeID": ["EMP014", "EMP037"],
        "Nationality": ["غير سعودي", "Saudi"],
    })
    result = get_saudi_status_by_record_id(df)
    expected_key_1 = "EMP-" + hashlib.sha256("EMP014".encode()).hexdigest()[:6].upper()
    expected_key_2 = "EMP-" + hashlib.sha256("EMP037".encode()).hexdigest()[:6].upper()
    assert result == {expected_key_1: False, expected_key_2: True}


def test_saudi_status_map_excludes_missing_id_or_nationality():
    df = pd.DataFrame({
        "EmployeeID": ["E1", None, "E3"],
        "Nationality": ["Saudi", "India", None],
    })
    result = get_saudi_status_by_record_id(df)
    assert len(result) == 1  # only E1 has both a usable ID and a classifiable nationality


def test_saudi_status_map_against_real_succession_fixture():
    """succession_test_data.csv (built for Phase 8) has both an EmployeeID
    and a Nationality column -- a real cross-link-eligible file. Confirm the
    map is non-empty and every value is a real boolean, never a guess."""
    assert _SUCCESSION_FIXTURE.exists(), f"expected fixture at {_SUCCESSION_FIXTURE}"
    df = pd.read_csv(_SUCCESSION_FIXTURE)
    result = get_saudi_status_by_record_id(df)
    assert result is not None
    assert len(result) > 0
    assert all(isinstance(v, bool) for v in result.values())
