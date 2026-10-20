"""
Tests for backend.core.procurement_intelligence_engine — Phase 33.

Fixture: procurement_transactions_test_data.csv — 40 purchase-order lines,
5 suppliers, 8 SKUs, 2025-11 to 2026-03. All expected figures below were
independently computed with pandas directly against this CSV (see the
build script this phase used), documented inline, not re-derived from the
engine.

Deliberately engineered cases:
  - BOLT-M8 sourced from Al-Rajhi Steel Supply (cheap, ~0.45) and Gulf
    Hardware Trading (pricier, ~0.55, +22.22%) -> cost-reduction flag.
  - MOTOR-5HP sourced from Precision Machinery Parts (~432.33) and Riyadh
    Industrial Supplies (~472.50, +9.29%) -> second cost-reduction flag.
  - HELMET (Gulf Hardware Trading) has a real +20.00% price rise over 5
    monthly POs -> price-trend flag.
  - GLOVES-L (National Safety Equipment Co) has a real -5.56% price
    decline over 5 monthly POs -> favorable price-trend flag.
  - PUMP-HP200 (Precision Machinery Parts) has only 2 POs -> suppressed
    for insufficient sample (below the 4-PO / 2-period floor).
  - Riyadh Industrial Supplies has NO delivery-date data at all, and its
    only price-trend pair is suppressed -> excluded from performance
    scoring entirely (zero components available).
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.core.procurement_intelligence_engine import (
    analyze_procurement_intelligence,
)

MAIN_FIXTURE = "procurement_transactions_test_data.csv"


@pytest.fixture
def main_df():
    return pd.read_csv(MAIN_FIXTURE)


def _item(items, **kwargs):
    for i in items:
        if all(getattr(i, k) == v for k, v in kwargs.items()):
            return i
    raise AssertionError(f"No item matching {kwargs}")


# ── Section 1: Supplier Spend Analysis ──────────────────────────────────────

class TestSupplierSpend:
    def test_hand_computed_totals(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        assert r.supplier_spend.available is True
        assert r.supplier_spend.total_spend_all_suppliers == pytest.approx(62282.1, abs=0.5)

    def test_hand_computed_per_supplier(self, main_df):
        """Al-Rajhi: sum(price*qty) across its 16 POs = 15221.00 (verified
        via pandas groupby)."""
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.supplier_spend.items, supplier="Al-Rajhi Steel Supply")
        assert item.total_spend == pytest.approx(15221.0, abs=0.5)
        assert item.n_pos == 16

    def test_category_breakdown_present(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.supplier_spend.items, supplier="Al-Rajhi Steel Supply")
        categories = {c.category for c in item.category_breakdown}
        assert categories == {"Hardware", "Consumables"}

    def test_not_available_without_supplier_or_sku(self):
        r = analyze_procurement_intelligence(pd.DataFrame({"Foo": [1, 2]}))
        assert r.supplier_spend.available is False


# ── Section 2: PO & Price Analysis ──────────────────────────────────────────

class TestPOPriceAnalysis:
    def test_hand_computed_price_history(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        assert r.po_price_analysis.available is True
        item = _item(r.po_price_analysis.items, supplier="Al-Rajhi Steel Supply", sku="BOLT-M8")
        assert item.n_pos == 5
        assert item.min_price == 0.44
        assert item.max_price == 0.46

    def test_price_points_sorted_chronologically(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.po_price_analysis.items, supplier="Gulf Hardware Trading", sku="HELMET")
        dates = [p.date for p in item.price_points]
        assert dates == sorted(dates)


# ── Section 3: Price Variance / Trend Tracking ──────────────────────────────

class TestPriceTrend:
    def test_hand_computed_helmet_rising_trend(self, main_df):
        """HELMET/Gulf: monthly avg prices 14.00 -> 14.50 -> 15.20 -> 16.00
        -> 16.80. Overall change = (16.80-14.00)/14.00 = +20.00%."""
        r = analyze_procurement_intelligence(main_df)
        assert r.price_trend.available is True
        item = _item(r.price_trend.items, supplier="Gulf Hardware Trading", sku="HELMET")
        assert item.n_pos == 5
        assert item.n_periods == 5
        assert item.overall_change_pct == pytest.approx(20.0, abs=0.05)

    def test_hand_computed_gloves_declining_trend(self, main_df):
        """GLOVES-L/National: 3.60 -> 3.40 over 5 periods = -5.56%."""
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.price_trend.items, supplier="National Safety Equipment Co", sku="GLOVES-L")
        assert item.overall_change_pct == pytest.approx(-5.56, abs=0.05)

    def test_period_variance_shape_matches_established_pattern(self, main_df):
        """Reuses payroll_budget_engine.py's variance field shape: period,
        prior_period, variance, variance_pct — sorted by absolute magnitude."""
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.price_trend.items, supplier="Gulf Hardware Trading", sku="HELMET")
        assert len(item.period_variances) == 4  # 5 periods -> 4 consecutive comparisons
        mags = [abs(v.price_variance_pct) for v in item.period_variances]
        assert mags == sorted(mags, reverse=True)

    def test_insufficient_sample_suppressed_not_guessed(self, main_df):
        """PUMP-HP200/Precision has only 2 POs -- below the 4-PO floor --
        must be suppressed, not shown as a 2-point trend."""
        r = analyze_procurement_intelligence(main_df)
        pairs = {(i.supplier, i.sku) for i in r.price_trend.items}
        assert ("Precision Machinery Parts", "PUMP-HP200") not in pairs
        assert r.price_trend.n_pairs_suppressed_insufficient_sample >= 1

    def test_min_sample_thresholds_disclosed(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        assert r.price_trend.min_periods_required == 2
        assert r.price_trend.min_pos_required == 4


# ── Section 4: Delivery / On-Time Performance ───────────────────────────────

class TestDeliveryPerformance:
    def test_hand_computed_on_time_pct(self, main_df):
        """Al-Rajhi: 16 POs with delivery data, 13 on-time (actual <=
        expected) -> 81.2%. Independently verified via pandas."""
        r = analyze_procurement_intelligence(main_df)
        assert r.delivery_performance.available is True
        item = _item(r.delivery_performance.items, supplier="Al-Rajhi Steel Supply")
        assert item.n_pos_with_delivery_data == 16
        assert item.n_on_time == 13
        assert item.on_time_pct == pytest.approx(81.2, abs=0.1)

    def test_worst_performer_precision_zero_percent(self, main_df):
        """Precision Machinery Parts: all 5 delivery-tracked POs were late
        -> 0.0% on-time (a real, if extreme, outcome from the fixture)."""
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.delivery_performance.items, supplier="Precision Machinery Parts")
        assert item.on_time_pct == 0.0

    def test_supplier_without_delivery_data_excluded_and_disclosed(self, main_df):
        """Riyadh Industrial Supplies has no ExpectedDeliveryDate/
        ActualDeliveryDate values at all -- must be listed as missing, not
        silently defaulted to some on-time percentage."""
        r = analyze_procurement_intelligence(main_df)
        assert "Riyadh Industrial Supplies" in r.delivery_performance.suppliers_without_delivery_data
        assert not any(i.supplier == "Riyadh Industrial Supplies" for i in r.delivery_performance.items)


# ── Section 5: Supplier Performance Scoring (constructed heuristic) ────────

class TestSupplierPerformanceScoring:
    def test_marked_as_constructed_heuristic_not_validated(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        assert r.supplier_performance.is_validated_instrument is False
        assert r.supplier_performance.confidence == "constructed_heuristic_not_validated"

    def test_hand_computed_composite_both_components(self, main_df):
        """Al-Rajhi: delivery=81.2, price_trend_component = avg(100-max(0,x))
        across its 3 eligible pairs (BOLT-M8 +2.27%, BOX-LARGE +1.12%,
        TAPE-ROLL +1.69%) = avg(97.73, 98.88, 98.31) = 98.31 (approx).
        Composite = 0.5*81.2 + 0.5*98.31 = 89.75 (approx, engine rounds)."""
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.supplier_performance.items, supplier="Al-Rajhi Steel Supply")
        assert set(item.components_used) == {"delivery_on_time_pct", "price_trend"}
        assert item.delivery_component == pytest.approx(81.2, abs=0.1)
        assert item.composite_score == pytest.approx(89.8, abs=0.3)

    def test_hand_computed_composite_delivery_only(self, main_df):
        """Precision Machinery Parts: both its price-trend pairs
        (PUMP-HP200 n=2, MOTOR-5HP n=3) are below the sample floor -> no
        price component. Composite = delivery component alone = 0.0."""
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.supplier_performance.items, supplier="Precision Machinery Parts")
        assert item.components_used == ["delivery_on_time_pct"]
        assert item.price_trend_component is None
        assert item.composite_score == 0.0

    def test_supplier_with_zero_components_excluded_not_force_scored(self, main_df):
        """Riyadh: no delivery data AND its only price-trend pair is
        suppressed -> must be excluded from scoring entirely."""
        r = analyze_procurement_intelligence(main_df)
        assert not any(i.supplier == "Riyadh Industrial Supplies" for i in r.supplier_performance.items)
        assert r.supplier_performance.n_suppliers_excluded_no_data == 1


# ── Section 6: Cost-Reduction Opportunity Flagging ──────────────────────────

class TestCostReduction:
    def test_hand_computed_bolt_m8_flag(self, main_df):
        """BOLT-M8: Al-Rajhi avg 0.45 (n=5) vs Gulf avg 0.55 (n=3) ->
        diff_pct = (0.55-0.45)/0.45*100 = 22.22%."""
        r = analyze_procurement_intelligence(main_df)
        assert r.cost_reduction.available is True
        item = _item(r.cost_reduction.items, sku="BOLT-M8")
        assert item.cheapest_supplier == "Al-Rajhi Steel Supply"
        assert item.cheapest_avg_price == pytest.approx(0.45, abs=0.005)
        assert item.priciest_supplier == "Gulf Hardware Trading"
        assert item.priciest_avg_price == pytest.approx(0.55, abs=0.005)
        assert item.price_diff_pct == pytest.approx(22.22, abs=0.1)

    def test_hand_computed_motor_5hp_flag(self, main_df):
        """MOTOR-5HP: Precision avg 432.33 (n=3) vs Riyadh avg 472.50 (n=2)
        -> diff_pct = 9.29%."""
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.cost_reduction.items, sku="MOTOR-5HP")
        assert item.price_diff_pct == pytest.approx(9.29, abs=0.1)

    def test_single_supplier_items_never_flagged(self, main_df):
        """HELMET, GLOVES-L, BEARING-6205, TAPE-ROLL, BOX-LARGE are each
        sourced from exactly ONE supplier -- no comparison possible, must
        never appear as a cost-reduction opportunity."""
        r = analyze_procurement_intelligence(main_df)
        flagged_skus = {i.sku for i in r.cost_reduction.items}
        assert flagged_skus == {"BOLT-M8", "MOTOR-5HP"}

    def test_observation_counts_disclosed(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        item = _item(r.cost_reduction.items, sku="BOLT-M8")
        assert item.cheapest_n_pos == 5
        assert item.priciest_n_pos == 3


# ── Section 7: Cross-module honest degradation ──────────────────────────────

class TestCrossModuleDifferentiation:
    """Proves this module never accidentally computes anything from
    Inventory (Phase 32), Financial (Phase 30), or Accounting (Phase 31)
    fixtures -- none has supplier + SKU + PO-shaped columns together."""

    def test_unavailable_on_inventory_fixture(self):
        df = pd.read_csv("inventory_transactions_test_data.csv")
        r = analyze_procurement_intelligence(df)
        assert r.supplier_spend.available is False

    def test_unavailable_on_phase30_fixture(self):
        df = pd.read_csv("financial_transactions_test_data.csv")
        r = analyze_procurement_intelligence(df)
        assert r.supplier_spend.available is False

    def test_unavailable_on_phase31_fixture(self):
        df = pd.read_csv("accounting_gl_test_data.csv")
        r = analyze_procurement_intelligence(df)
        assert r.supplier_spend.available is False

    def test_unavailable_on_employee_data(self):
        df = pd.read_csv("test_employee_data.csv")
        r = analyze_procurement_intelligence(df)
        assert r.supplier_spend.available is False

    def test_never_fabricates_on_empty_data(self):
        r = analyze_procurement_intelligence(pd.DataFrame())
        assert r.supplier_spend.available is False
        assert r.po_price_analysis.available is False
        assert r.price_trend.available is False
        assert r.delivery_performance.available is False
        assert r.supplier_performance.available is False
        assert r.cost_reduction.available is False


# ── Section 8: Bundle + serialization sanity ────────────────────────────────

class TestBundleAndSerialization:
    def test_analyze_bundles_all_six(self, main_df):
        r = analyze_procurement_intelligence(main_df)
        assert r.supplier_spend.available is True
        assert r.po_price_analysis.available is True
        assert r.price_trend.available is True
        assert r.delivery_performance.available is True
        assert r.supplier_performance.available is True
        assert r.cost_reduction.available is True

    def test_to_dict_contains_all_sections(self, main_df):
        from backend.core.procurement_intelligence_engine import procurement_intelligence_to_dict
        r = analyze_procurement_intelligence(main_df)
        d = procurement_intelligence_to_dict(r)
        for key in ["supplier_spend", "po_price_analysis", "price_trend", "delivery_performance", "supplier_performance", "cost_reduction", "disclaimer_en", "disclaimer_ar", "sources"]:
            assert key in d

    def test_never_raises_on_malformed_input(self):
        df = pd.DataFrame({"SupplierName": [None, None], "SKU": ["x", "y"], "UnitPrice": ["a", "b"]})
        r = analyze_procurement_intelligence(df)
        assert r.supplier_spend.available is False
