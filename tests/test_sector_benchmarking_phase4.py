"""
Phase 35.4 — Sector-based benchmarking tests.

Covers the two salary-benchmark tiers financial_intelligence_engine.py now
exposes: the REAL, GASTAT-cited EMPLOYMENT_SECTOR_SALARY_SAR table, and the
existing industry-vertical SECTOR_SALARY_SAR table now honestly labeled
"uncalibrated_generic_estimate" rather than presented as sourced. Also
covers employment-sector inference from dataset metadata and the "no silent
guessing" fallback requirement.

Run: py -m pytest tests/test_sector_benchmarking_phase4.py -v
"""

from __future__ import annotations

import pytest

from backend.core import financial_intelligence_engine as fie


# ── Honest labeling of the uncalibrated industry-vertical table ────────────

def test_industry_vertical_table_is_labeled_uncalibrated():
    assert fie.SECTOR_BENCHMARK_CONFIDENCE == "uncalibrated_generic_estimate"
    assert "not sourced" in fie.SECTOR_BENCHMARK_DISCLAIMER.lower() or "no freely citable" in fie.SECTOR_BENCHMARK_DISCLAIMER.lower()


def test_default_departure_cost_carries_uncalibrated_label():
    """Calling with only the old-style industry-vertical `sector` param (no
    employment_sector, no observed salary) must be honestly labeled."""
    d = fie.estimate_departure_cost("mid", "banking")
    assert d.salary_benchmark_confidence == fie.SECTOR_BENCHMARK_CONFIDENCE


# ── Real, cited employment-sector benchmark ─────────────────────────────────

def test_employment_sector_table_has_real_citation():
    assert "GASTAT" in fie.EMPLOYMENT_SECTOR_SOURCE
    assert "stats.gov.sa" in fie.EMPLOYMENT_SECTOR_SOURCE
    assert fie.EMPLOYMENT_SECTOR_BENCHMARK_CONFIDENCE == "gastat_official_2018"


def test_employment_sector_table_has_four_real_categories():
    assert set(fie.EMPLOYMENT_SECTOR_SALARY_SAR) == {
        "public", "private", "non_profit", "international_regional",
    }
    # Sanity: these are the actual published GASTAT figures (SAR/month).
    assert fie.EMPLOYMENT_SECTOR_SALARY_SAR["public"] == 11_198.0
    assert fie.EMPLOYMENT_SECTOR_SALARY_SAR["private"] == 7_339.0
    assert fie.EMPLOYMENT_SECTOR_SALARY_SAR["non_profit"] == 4_750.0
    assert fie.EMPLOYMENT_SECTOR_SALARY_SAR["international_regional"] == 16_257.0


@pytest.mark.parametrize("employment_sector", ["public", "private", "non_profit", "international_regional"])
def test_departure_cost_with_employment_sector_uses_gastat_confidence(employment_sector):
    d = fie.estimate_departure_cost("mid", "diversified", employment_sector=employment_sector)
    assert d.salary_benchmark_confidence == "gastat_official_2018"
    expected_salary = round(
        fie.EMPLOYMENT_SECTOR_SALARY_SAR[employment_sector] * fie.SENIORITY_SALARY_MULT["mid"], 0
    )
    assert d.monthly_salary_sar == expected_salary


def test_invalid_employment_sector_falls_back_to_uncalibrated_not_silent_default():
    """An unrecognised employment_sector string must NOT be silently treated
    as a real GASTAT sector — it must fall back to the uncalibrated table."""
    d = fie.estimate_departure_cost("mid", "diversified", employment_sector="not_a_real_sector")
    assert d.salary_benchmark_confidence == fie.SECTOR_BENCHMARK_CONFIDENCE


# ── Precedence: observed > employment_sector > industry-vertical ───────────

def test_observed_salary_wins_over_employment_sector():
    salary = fie.estimate_monthly_salary(
        "diversified", "mid", observed_salary_sar=25_000.0, employment_sector="public",
    )
    assert salary == 25_000.0
    assert fie.salary_benchmark_confidence_for(25_000.0, "public") == "observed"


def test_employment_sector_wins_over_industry_vertical():
    salary_with_sector = fie.estimate_monthly_salary("banking", "mid", employment_sector="private")
    salary_without = fie.estimate_monthly_salary("banking", "mid")
    # banking (uncalibrated, 12,000 base) vs private (GASTAT, 7,339 base) differ.
    assert salary_with_sector != salary_without
    assert salary_with_sector == pytest.approx(fie.EMPLOYMENT_SECTOR_SALARY_SAR["private"] * fie.SENIORITY_SALARY_MULT["mid"])


# ── Employment-sector inference — real signal or explicit None, never a guess ──

def test_infer_employment_sector_from_department_names():
    assert fie.infer_employment_sector_from_metadata([{"group_value": "Ministry of Finance"}]) == "public"
    assert fie.infer_employment_sector_from_metadata([{"group_value": "City Municipality"}]) == "public"
    assert fie.infer_employment_sector_from_metadata([{"group_value": "Al-Noor Charity Foundation"}]) == "non_profit"
    assert fie.infer_employment_sector_from_metadata([{"group_value": "UN Regional Office"}]) == "international_regional"


def test_infer_employment_sector_from_explicit_column_values():
    assert fie.infer_employment_sector_from_metadata(
        sector_column_values=["Government", "Government", "Public Sector"]
    ) == "public"
    assert fie.infer_employment_sector_from_metadata(
        sector_column_values=["Private Company LLC", "Private Corp"]
    ) == "private"
    assert fie.infer_employment_sector_from_metadata(
        sector_column_values=["Registered NGO"]
    ) == "non_profit"


def test_infer_employment_sector_returns_none_not_a_guess_when_no_signal():
    """No fabrication: absence of a real signal must return None, not a
    silently-defaulted sector."""
    result = fie.infer_employment_sector_from_metadata([{"group_value": "Sales"}, {"group_value": "Engineering"}])
    assert result is None


def test_infer_employment_sector_none_input_returns_none():
    assert fie.infer_employment_sector_from_metadata(None) is None
    assert fie.infer_employment_sector_from_metadata([]) is None


# ── End-to-end: workforce exposure honestly reports its confidence ─────────

def test_workforce_exposure_reports_confidence_in_dict():
    exp = fie.estimate_workforce_financial_exposure(30, employment_sector="private")
    d = fie.workforce_exposure_to_dict(exp)
    assert d["salary_benchmark_confidence"] == "gastat_official_2018"

    exp2 = fie.estimate_workforce_financial_exposure(30)
    d2 = fie.workforce_exposure_to_dict(exp2)
    assert d2["salary_benchmark_confidence"] == "uncalibrated_generic_estimate"


def test_departure_cost_to_dict_includes_confidence():
    d = fie.departure_cost_to_dict(fie.estimate_departure_cost("mid", "diversified"))
    assert "salary_benchmark_confidence" in d


# Phase 40: the report-exporter follow-up tests (executive_pdf_exporter.py,
# executive_pptx_exporter.py, executive_slide_exporter.py all threading
# employment_sector through) were removed along with those 3 modules —
# see PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.
