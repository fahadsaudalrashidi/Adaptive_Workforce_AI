"""
Phase 34 — Financial Intelligence Engine consolidation tests.

Covers:
  1. Real computed-value assertions against the canonical financial module
     (backend/core/financial_intelligence_engine.py).
  2. Traceability assertions proving every previously-divergent call site
     (the 3 report exporters, workforce_simulation_engine.py, and
     roi_estimation_engine.py) now imports its financial figures from this
     single module instead of a locally hardcoded formula.

Run: py -m pytest tests/test_financial_intelligence_engine.py -v
"""

from __future__ import annotations

import inspect

import pytest

from backend.core import financial_intelligence_engine as fie


# ── estimate_monthly_salary ─────────────────────────────────────────────────

def test_monthly_salary_prefers_observed_data_over_estimate():
    """Real uploaded salary data must always win over the sector/seniority guess."""
    observed = fie.estimate_monthly_salary("banking", "executive", observed_salary_sar=11_111.0)
    assert observed == 11_111.0


def test_monthly_salary_falls_back_to_sector_seniority_table():
    salary = fie.estimate_monthly_salary("oil_gas", "senior")
    expected = fie.SECTOR_SALARY_SAR["oil_gas"] * fie.SENIORITY_SALARY_MULT["senior"]
    assert salary == pytest.approx(expected)


def test_monthly_salary_unknown_sector_and_seniority_default_safely():
    salary = fie.estimate_monthly_salary("not_a_real_sector", "not_a_real_seniority")
    expected = fie.SECTOR_SALARY_SAR["diversified"] * fie.SENIORITY_SALARY_MULT["mid"]
    assert salary == pytest.approx(expected)


# ── compute_departure_cost_components ───────────────────────────────────────

def test_departure_cost_components_cover_all_nine_components():
    components = fie.compute_departure_cost_components("mid", 10_000.0, n=1)
    assert {c.component_id for c in components} == set(fie.COST_MATRIX.keys())
    assert len(components) == 9


def test_departure_cost_components_scale_linearly_with_headcount():
    single = fie.compute_departure_cost_components("mid", 10_000.0, n=1)
    quintuple = fie.compute_departure_cost_components("mid", 10_000.0, n=5)
    for c1, c5 in zip(single, quintuple):
        assert c5.cost_low_sar == pytest.approx(c1.cost_low_sar * 5)
        assert c5.cost_high_sar == pytest.approx(c1.cost_high_sar * 5)


def test_departure_cost_components_low_never_exceeds_high():
    for seniority in fie.SENIORITY_SALARY_MULT:
        for c in fie.compute_departure_cost_components(seniority, 10_000.0):
            assert c.cost_low_sar <= c.cost_high_sar
            assert c.multiplier_low <= c.multiplier_high


# ── estimate_departure_cost ──────────────────────────────────────────────────

def test_departure_cost_mid_is_between_low_and_high():
    d = fie.estimate_departure_cost("mid", "diversified")
    assert d.cost_low_sar < d.cost_mid_sar < d.cost_high_sar
    assert d.cost_mid_sar == pytest.approx((d.cost_low_sar + d.cost_high_sar) / 2)


def test_departure_cost_matches_sum_of_components():
    d = fie.estimate_departure_cost("senior", "banking")
    assert d.cost_low_sar == pytest.approx(sum(c.cost_low_sar for c in d.components))
    assert d.cost_high_sar == pytest.approx(sum(c.cost_high_sar for c in d.components))


def test_departure_cost_increases_with_seniority():
    """Executive departures must cost more than junior departures, all else equal."""
    junior = fie.estimate_departure_cost("junior", "diversified")
    executive = fie.estimate_departure_cost("executive", "diversified")
    assert executive.cost_mid_sar > junior.cost_mid_sar


def test_departure_cost_carries_citations():
    d = fie.estimate_departure_cost()
    assert len(d.sources) >= 3
    assert any("Cascio" in s for s in d.sources)


# ── estimate_workforce_financial_exposure (the function that replaced
#    `at_risk * 120_000` everywhere) ─────────────────────────────────────────

def test_workforce_exposure_zero_at_risk_is_zero_exposure():
    e = fie.estimate_workforce_financial_exposure(0)
    assert e.exposure_sar == 0
    assert e.estimated_retained_count == 0
    assert e.potential_savings_sar == 0


def test_workforce_exposure_scales_linearly_with_at_risk_count():
    e10 = fie.estimate_workforce_financial_exposure(10, "diversified", "mid")
    e20 = fie.estimate_workforce_financial_exposure(20, "diversified", "mid")
    assert e20.exposure_sar == pytest.approx(e10.exposure_sar * 2)


def test_workforce_exposure_monthly_is_exposure_over_twelve():
    e = fie.estimate_workforce_financial_exposure(25, "diversified", "mid")
    # monthly_exposure_sar is rounded to the nearest whole SAR, so allow for
    # up to 1 SAR of rounding drift against the unrounded division.
    assert e.monthly_exposure_sar == pytest.approx(e.exposure_sar / 12, abs=1.0)


def test_workforce_exposure_retained_count_uses_retention_rate():
    e = fie.estimate_workforce_financial_exposure(100, retention_rate=0.30)
    assert e.estimated_retained_count == 30


def test_workforce_exposure_savings_uses_savings_rate():
    e = fie.estimate_workforce_financial_exposure(100, "diversified", "mid", savings_rate=0.40)
    assert e.potential_savings_sar == pytest.approx(e.exposure_sar * 0.40)


def test_workforce_exposure_default_rates_match_module_constants():
    """Guards against silent drift between the documented defaults and behaviour."""
    e = fie.estimate_workforce_financial_exposure(50)
    assert e.retention_rate == fie.DEFAULT_RETENTION_RATE
    assert e.potential_savings_sar == pytest.approx(e.exposure_sar * fie.DEFAULT_SAVINGS_RATE)


# ── build_retention_roi_scenarios ───────────────────────────────────────────

def test_roi_scenarios_returns_three_tiers_in_order():
    scenarios = fie.build_retention_roi_scenarios(40, 60_000.0, 120_000.0, 16_000.0)
    assert [s.scenario_id for s in scenarios] == ["conservative", "targeted", "comprehensive"]


def test_roi_scenarios_more_aggressive_tier_retains_more_people():
    scenarios = fie.build_retention_roi_scenarios(100, 60_000.0, 120_000.0, 16_000.0)
    conservative, targeted, comprehensive = scenarios
    assert conservative.n_retained_low <= targeted.n_retained_low <= comprehensive.n_retained_low


def test_roi_scenarios_zero_at_risk_does_not_crash():
    scenarios = fie.build_retention_roi_scenarios(0, 0.0, 0.0, 10_000.0)
    assert len(scenarios) == 3
    for s in scenarios:
        assert s.n_retained_low == 0


# ── sector / seniority inference ────────────────────────────────────────────

@pytest.mark.parametrize("dept_name,expected_sector", [
    ("Retail Banking Operations", "banking"),
    ("Oil & Gas Exploration", "oil_gas"),
    ("Telecom Network Engineering", "telecom"),
    ("Ministry of Labour Affairs", "government"),
    ("Central Hospital Cardiology", "healthcare"),
    ("Retail Store Operations", "retail"),
])
def test_sector_inference_from_department_keywords(dept_name, expected_sector):
    depts = [{"group_value": dept_name, "total_records": 10}]
    assert fie.infer_sector_from_departments(depts) == expected_sector


def test_sector_inference_defaults_to_diversified_when_no_signal():
    assert fie.infer_sector_from_departments([{"group_value": "Team Alpha"}]) == "diversified"
    assert fie.infer_sector_from_departments(None) == "diversified"
    assert fie.infer_sector_from_departments([]) == "diversified"


@pytest.mark.parametrize("dept_name,expected_seniority", [
    ("Chief Executive Office", "executive"),
    ("Senior Engineering Managers", "senior"),
    ("Junior Analyst Pool", "junior"),
])
def test_seniority_inference_from_department_keywords(dept_name, expected_seniority):
    depts = [{"group_value": dept_name}]
    assert fie.infer_seniority_from_signals(depts) == expected_seniority


def test_seniority_inference_defaults_to_mid():
    assert fie.infer_seniority_from_signals(None) == "mid"
    assert fie.infer_seniority_from_signals([{"group_value": "Operations"}]) == "mid"


# ── serialization helpers ───────────────────────────────────────────────────

def test_workforce_exposure_to_dict_is_json_safe():
    e = fie.estimate_workforce_financial_exposure(15)
    d = fie.workforce_exposure_to_dict(e)
    assert d["n_at_risk"] == 15
    assert d["exposure_sar"] == e.exposure_sar
    assert isinstance(d["sources"], list) and len(d["sources"]) > 0


def test_departure_cost_to_dict_includes_all_components():
    d = fie.departure_cost_to_dict(fie.estimate_departure_cost("mid", "diversified"))
    assert len(d["components"]) == 9


# ── Traceability: every previously-divergent call site now imports from
#    this single module instead of hardcoding its own formula ─────────────
#
# Phase 40: executive_pdf_exporter.py, executive_pptx_exporter.py,
# executive_slide_exporter.py, workforce_simulation_engine.py, and
# executive_roi_engine.py were removed along with employee_risk_scoring.py
# and the pages they exclusively served — their entries here (and the 2
# tests below that inspected them specifically for a stale hardcoded
# formula) were removed with them. roi_estimation_engine.py is unrelated
# (kept, still tested in tests/test_phase6_enterprise_deployment.py) and
# remains covered here. See PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.

_CONSOLIDATED_CALL_SITES = [
    "backend.core.roi_estimation_engine",
]


@pytest.mark.parametrize("module_name", _CONSOLIDATED_CALL_SITES)
def test_call_site_imports_from_canonical_financial_module(module_name):
    """
    Each surviving module that formerly hardcoded its own financial constant
    (roi_estimation_engine's flat SAR 8,000/month default) must import at
    least one name from financial_intelligence_engine. This is a structural
    regression guard: if someone reintroduces a hardcoded formula instead of
    calling the canonical module, this test does NOT catch that directly,
    but removing the import entirely (a strong signal of re-diverging) will
    fail this test immediately.
    """
    import importlib
    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    assert "financial_intelligence_engine" in source, (
        f"{module_name} no longer imports from the canonical financial module — "
        "if a financial formula was reintroduced locally, consolidate it back "
        "into backend/core/financial_intelligence_engine.py."
    )
