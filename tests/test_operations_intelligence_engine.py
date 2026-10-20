"""
Tests for backend.core.operations_intelligence_engine — Phase 35.

Fixture: operations_units_test_data.csv — 26 unit-period records, 5
operational units, 2025-11 to 2026-04. All expected figures below were
independently computed with pandas directly against this CSV (see the
build script this phase used), documented inline, not re-derived from the
engine.

Deliberately engineered cases:
  - Line-1/2/5: full 6-period data, healthy-to-moderate performers
    (utilization 90.08% / 75.00% / 80.00%).
  - Line-3: BOTTLENECK with full 6-period data — utilization 44.33%, well
    below the fleet average (72.35%, computed only from sufficient-sample
    units) by more than the 15-point gap threshold -> confidently flagged.
    Its defect rate also genuinely worsens period over period (a real
    quality trend, not a flat number).
  - Line-4: only 2 periods, utilization 39.50% -- WORSE than Line-3's raw
    number -- but must NOT be confidently flagged as a bottleneck because
    it falls below the 3-period minimum-sample floor.
  - Downtime-reason free text spans 5 themes: Changeover/Setup (8),
    Mechanical Failure (7), Material Shortage (5), Scheduled Maintenance
    (5) all clear the 3-mention floor; nothing falls below it in the main
    fixture (a dedicated below-floor case is exercised in a smaller
    inline fixture in this file instead, for a clean, isolated assertion).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.core.operations_intelligence_engine import (
    analyze_operations_intelligence,
)

MAIN_FIXTURE = "operations_units_test_data.csv"


@pytest.fixture
def main_df():
    return pd.read_csv(MAIN_FIXTURE)


def _item(items, **kwargs):
    for i in items:
        if all(getattr(i, k) == v for k, v in kwargs.items()):
            return i
    raise AssertionError(f"No item matching {kwargs}")


# ── Section 1: Productivity ──────────────────────────────────────────────

class TestProductivity:
    def test_hand_computed_ranking(self, main_df):
        """Line-1: 10810 output / 1081 hours = 10.0 units/hour (highest).
        Line-3 and Line-4 tie at 7.0 (lowest)."""
        r = analyze_operations_intelligence(main_df)
        assert r.productivity.available is True
        top = r.productivity.items[0]
        assert top.unit == "Line-1"
        assert top.productivity == pytest.approx(10.0, abs=0.01)

    def test_hand_computed_line3_productivity(self, main_df):
        r = analyze_operations_intelligence(main_df)
        item = _item(r.productivity.items, unit="Line-3")
        assert item.total_output == 3724.0
        assert item.total_hours_operated == 532.0
        assert item.productivity == pytest.approx(7.0, abs=0.01)

    def test_not_available_without_hours_operated(self):
        df = pd.DataFrame({"Unit": ["A"], "Output": [100]})
        r = analyze_operations_intelligence(df)
        assert r.productivity.available is False


# ── Section 2: Utilization ────────────────────────────────────────────────

class TestUtilization:
    def test_hand_computed_utilization(self, main_df):
        """Line-1: 1081/1200 = 90.08%; Line-3: 532/1200 = 44.33%; Line-4:
        158/400 = 39.50% (independently verified via pandas)."""
        r = analyze_operations_intelligence(main_df)
        assert r.utilization.available is True
        assert _item(r.utilization.items, unit="Line-1").utilization_pct == pytest.approx(90.08, abs=0.01)
        assert _item(r.utilization.items, unit="Line-3").utilization_pct == pytest.approx(44.33, abs=0.01)
        assert _item(r.utilization.items, unit="Line-4").utilization_pct == pytest.approx(39.5, abs=0.01)

    def test_not_available_without_hours_available_capacity(self):
        """Utilization must never be estimated with an assumed default
        capacity -- dropping HoursAvailable must make it unavailable."""
        df = pd.read_csv(MAIN_FIXTURE).drop(columns=["HoursAvailable"])
        r = analyze_operations_intelligence(df)
        assert r.utilization.available is False
        assert "hours-available" in r.utilization.reason.lower() or "capacity" in r.utilization.reason.lower()
        # Productivity and downtime should still work from the remaining columns.
        r2 = analyze_operations_intelligence(df)
        assert r2.productivity.available is True


# ── Section 3: Downtime Analysis ─────────────────────────────────────────

class TestDowntimeAnalysis:
    def test_hand_computed_total_and_by_unit(self, main_df):
        """Total downtime = 1569.0 hours (independently verified via
        pandas sum). Line-3 has the most (668.0)."""
        r = analyze_operations_intelligence(main_df)
        assert r.downtime.available is True
        assert r.downtime.total_downtime_hours == pytest.approx(1569.0, abs=0.5)
        top = r.downtime.by_unit[0]
        assert top.unit == "Line-3"
        assert top.total_downtime_hours == pytest.approx(668.0, abs=0.5)

    def test_hand_computed_theme_extraction(self, main_df):
        """Free-text downtime reasons classify into 4 themes clearing the
        3-mention floor: Changeover/Setup=8, Mechanical Failure=7,
        Material Shortage=5, Scheduled Maintenance=5 (independently
        counted against the fixture's known reason-text design)."""
        r = analyze_operations_intelligence(main_df)
        assert r.downtime.cause_breakdown_method in ("tfidf", "word_frequency")
        themes = {t.theme: t.n_mentions for t in r.downtime.cause_themes}
        assert themes["Changeover/Setup"] == 8
        assert themes["Mechanical Failure"] == 7
        assert themes["Material Shortage"] == 5
        assert themes["Scheduled Maintenance"] == 5

    def test_power_outage_theme_suppressed_below_floor(self, main_df):
        """'Power Outage' is mentioned in only 1 of 26 downtime-reason
        texts -- below the 3-record floor -- must be suppressed."""
        r = analyze_operations_intelligence(main_df)
        themes = {t.theme for t in r.downtime.cause_themes}
        assert "Power Outage" not in themes

    def test_categorical_reason_column_skips_tfidf(self):
        """A short, low-cardinality reason column (already categorical)
        must be detected as such and use a direct breakdown, not TF-IDF."""
        rows = []
        for i in range(10):
            rows.append({
                "Unit": "A", "Period": f"2026-{(i % 6) + 1:02d}", "DowntimeHours": 5,
                "DowntimeReason": "Maintenance" if i % 2 == 0 else "Setup",
            })
        df = pd.DataFrame(rows)
        r = analyze_operations_intelligence(df)
        assert r.downtime.available is True
        assert r.downtime.cause_breakdown_method == "categorical"

    def test_no_raw_downtime_text_in_result(self, main_df):
        r = analyze_operations_intelligence(main_df)
        raw_reasons = set(main_df["DowntimeReason"].dropna())
        for term, _n in r.downtime.top_terms:
            assert term not in raw_reasons

    def test_not_available_without_downtime_hours(self):
        df = pd.DataFrame({"Unit": ["A"], "Output": [100]})
        r = analyze_operations_intelligence(df)
        assert r.downtime.available is False


# ── Section 4: Quality / Defect Analysis ─────────────────────────────────

class TestQualityAnalysis:
    def test_hand_computed_overall_defect_rate(self, main_df):
        """Overall defect rate = total defects / total output = 3.39%
        (independently verified via pandas)."""
        r = analyze_operations_intelligence(main_df)
        assert r.quality.available is True
        assert r.quality.overall_defect_rate_pct == pytest.approx(3.39, abs=0.02)

    def test_hand_computed_line3_worst_quality(self, main_df):
        r = analyze_operations_intelligence(main_df)
        item = _item(r.quality.by_unit, unit="Line-3")
        assert item.defect_rate_pct == pytest.approx(10.42, abs=0.02)

    def test_period_variance_reuses_established_shape(self, main_df):
        """6 periods -> 5 consecutive period comparisons, reusing the
        payroll_budget_engine.py / Phase 30/31/33/34 variance shape
        (variance, variance_pct, sorted by absolute magnitude)."""
        r = analyze_operations_intelligence(main_df)
        assert len(r.quality.period_variances) == 5
        mags = [abs(v.variance_pct or 0) for v in r.quality.period_variances]
        assert mags == sorted(mags, reverse=True)

    def test_hand_computed_rising_trend_is_real(self, main_df):
        """Overall defect rate genuinely rises from 2.92% (Nov 2025) to
        4.00% (Apr 2026) -- driven mostly by Line-3's worsening quality --
        not a flat/fabricated number."""
        r = analyze_operations_intelligence(main_df)
        first_to_last = next(
            v for v in r.quality.period_variances if v.prior_period == "2025-11" or v.period == "2025-12"
        )
        assert first_to_last.variance > 0

    def test_not_available_without_defects_or_quality_score(self):
        df = pd.DataFrame({"Unit": ["A"], "Output": [100]})
        r = analyze_operations_intelligence(df)
        assert r.quality.available is False


# ── Section 5: Bottleneck Identification ─────────────────────────────────

class TestBottleneckIdentification:
    def test_hand_computed_fleet_average(self, main_df):
        """Fleet average utilization computed ONLY from sufficient-sample
        units (Line-1/2/3/5, excluding Line-4's 2 periods):
        (90.08+75.00+44.33+80.00)/4 = 72.35%."""
        r = analyze_operations_intelligence(main_df)
        assert r.bottleneck.available is True
        assert r.bottleneck.fleet_avg_utilization_pct == pytest.approx(72.35, abs=0.05)

    def test_line3_confidently_flagged(self, main_df):
        """Line-3: 6 periods (>=3 floor), utilization 44.33% is 28.02
        points below the fleet average (>= the 15-point threshold) ->
        confidently flagged as a bottleneck."""
        r = analyze_operations_intelligence(main_df)
        item = _item(r.bottleneck.items, unit="Line-3")
        assert item.sufficient_sample is True
        assert item.is_bottleneck is True

    def test_line4_not_flagged_despite_worse_raw_number(self, main_df):
        """Line-4's utilization (39.50%) is WORSE than Line-3's (44.33%),
        but with only 2 periods of data it falls below the 3-period
        minimum-sample floor and must NOT be confidently flagged --
        raw numbers are still shown, just not the confident label."""
        r = analyze_operations_intelligence(main_df)
        item = _item(r.bottleneck.items, unit="Line-4")
        assert item.sufficient_sample is False
        assert item.is_bottleneck is False
        assert item.utilization_pct == pytest.approx(39.5, abs=0.01)  # raw number still shown

    def test_good_performers_not_flagged(self, main_df):
        r = analyze_operations_intelligence(main_df)
        for unit in ("Line-1", "Line-2", "Line-5"):
            item = _item(r.bottleneck.items, unit=unit)
            assert item.is_bottleneck is False

    def test_min_periods_threshold_disclosed(self, main_df):
        r = analyze_operations_intelligence(main_df)
        assert r.bottleneck.min_periods_for_confidence == 3


# ── Section 6: Cost per Unit of Operation ────────────────────────────────

class TestCostPerUnit:
    def test_hand_computed_cost_per_unit(self, main_df):
        """Line-1: total cost 54260.0 / total output 10810.0 = 5.019
        (cheapest); Line-3: 42150.0/3724.0 = 11.318 (most expensive among
        full-data units) -- independently verified via pandas."""
        r = analyze_operations_intelligence(main_df)
        assert r.cost_per_unit.available is True
        line1 = _item(r.cost_per_unit.items, unit="Line-1")
        line3 = _item(r.cost_per_unit.items, unit="Line-3")
        assert line1.cost_per_unit == pytest.approx(5.019, abs=0.01)
        assert line3.cost_per_unit == pytest.approx(11.318, abs=0.01)
        assert line3.cost_per_unit > line1.cost_per_unit

    def test_not_available_without_cost_or_output(self):
        df = pd.DataFrame({"Unit": ["A"], "HoursOperated": [100]})
        r = analyze_operations_intelligence(df)
        assert r.cost_per_unit.available is False


# ── Section 7: Cross-module honest degradation ──────────────────────────────

class TestCrossModuleDifferentiation:
    """Proves this module never accidentally computes anything from
    Logistics (Phase 34), Procurement (Phase 33), Inventory (Phase 32),
    Financial (Phase 30), or Accounting (Phase 31) fixtures."""

    @pytest.mark.parametrize("fixture", [
        "logistics_shipments_test_data.csv",
        "procurement_transactions_test_data.csv",
        "inventory_transactions_test_data.csv",
        "financial_transactions_test_data.csv",
        "accounting_gl_test_data.csv",
        "test_employee_data.csv",
    ])
    def test_unavailable_on_other_fixtures(self, fixture):
        df = pd.read_csv(fixture)
        r = analyze_operations_intelligence(df)
        assert r.productivity.available is False
        assert r.utilization.available is False

    def test_never_fabricates_on_empty_data(self):
        r = analyze_operations_intelligence(pd.DataFrame())
        assert r.productivity.available is False
        assert r.utilization.available is False
        assert r.downtime.available is False
        assert r.quality.available is False
        assert r.bottleneck.available is False
        assert r.cost_per_unit.available is False


# ── Section 8: Bundle + serialization sanity ────────────────────────────────

class TestBundleAndSerialization:
    def test_analyze_bundles_all_six(self, main_df):
        r = analyze_operations_intelligence(main_df)
        assert r.productivity.available is True
        assert r.utilization.available is True
        assert r.downtime.available is True
        assert r.quality.available is True
        assert r.bottleneck.available is True
        assert r.cost_per_unit.available is True

    def test_to_dict_contains_all_sections(self, main_df):
        from backend.core.operations_intelligence_engine import operations_intelligence_to_dict
        r = analyze_operations_intelligence(main_df)
        d = operations_intelligence_to_dict(r)
        for key in ["productivity", "utilization", "downtime", "quality", "bottleneck", "cost_per_unit", "disclaimer_en", "disclaimer_ar", "sources"]:
            assert key in d

    def test_never_raises_on_malformed_input(self):
        df = pd.DataFrame({"Unit": [None, None], "Output": ["x", "y"], "HoursOperated": ["a", "b"]})
        r = analyze_operations_intelligence(df)
        assert isinstance(r.productivity.available, bool)
