"""
Tests for backend.core.logistics_intelligence_engine — Phase 34.

Fixture: logistics_shipments_test_data.csv — 60 shipments, 4 carriers, 4
routes, 2025-11 to 2026-04. All expected figures below were independently
computed with pandas directly against this CSV (see the build script this
phase used), documented inline, not re-derived from the engine.

Deliberately engineered cases:
  - 4 carriers with genuinely different on-time rates and costs: DHL Saudi
    (92.3% on-time, premium SAR 67.50 avg), SMSA Express (86.7%, SAR
    44.81), Aramex (71.4%, cheap SAR 35.75), Fetchr Logistics (58.3%,
    SAR 40.50) -- for item 4's carrier comparison.
  - Delays concentrated on Fetchr Logistics x Riyadh-Dammam (5 late
    shipments, avg 6.0 days late) vs. every other carrier/route
    combination below the 3-late-shipment concentration floor except
    Aramex x Dammam-Khobar (4 late) -- for item 5's concentration flag.
  - 11 returned shipments with reason text spanning 3 themes at exactly
    3 mentions each (Damaged in Transit, Wrong Item Shipped, Defective
    Product) plus a 4th theme (Late Delivery) at only 2 mentions --
    deliberately below the 3-shipment suppression floor -- for item 6.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.core.logistics_intelligence_engine import (
    analyze_logistics_intelligence,
)

MAIN_FIXTURE = "logistics_shipments_test_data.csv"


@pytest.fixture
def main_df():
    return pd.read_csv(MAIN_FIXTURE)


def _item(items, **kwargs):
    for i in items:
        if all(getattr(i, k) == v for k, v in kwargs.items()):
            return i
    raise AssertionError(f"No item matching {kwargs}")


# ── Section 1: Shipment Volume & Status Overview ────────────────────────────

class TestShipmentStatus:
    def test_hand_computed_status_counts(self, main_df):
        """Status value_counts(): Delivered=43, Returned=11, In Transit=4,
        Delayed=2. Total=60."""
        r = analyze_logistics_intelligence(main_df)
        assert r.shipment_status.available is True
        assert r.shipment_status.n_shipments_total == 60
        counts = {c.status: c.n for c in r.shipment_status.status_counts}
        assert counts == {"delivered": 43, "returned": 11, "in_transit": 4, "delayed": 2}

    def test_not_available_without_status_column(self):
        df = pd.DataFrame({"Carrier": ["X"], "Cost": [10]})
        r = analyze_logistics_intelligence(df)
        assert r.shipment_status.available is False


# ── Section 2: Delivery Time / On-Time Performance (overall) ───────────────

class TestDeliveryTime:
    def test_hand_computed_overall_on_time(self, main_df):
        """54 shipments have both expected+actual dates (43 delivered + 11
        returned; the 4 in-transit + 2 delayed rows have no actual date).
        42 are on time (actual<=expected) -> 77.8%."""
        r = analyze_logistics_intelligence(main_df)
        assert r.delivery_time.available is True
        assert r.delivery_time.n_with_complete_dates == 54
        assert r.delivery_time.n_on_time == 42
        assert r.delivery_time.on_time_pct == pytest.approx(77.8, abs=0.1)

    def test_not_available_without_delivery_dates(self):
        df = pd.DataFrame({"Carrier": ["X", "Y"], "Status": ["Delivered", "Delivered"]})
        r = analyze_logistics_intelligence(df)
        assert r.delivery_time.available is False


# ── Section 3: Shipping Cost Analysis ────────────────────────────────────────

class TestShippingCost:
    def test_hand_computed_totals(self, main_df):
        r = analyze_logistics_intelligence(main_df)
        assert r.shipping_cost.available is True
        assert r.shipping_cost.total_cost == pytest.approx(2801.0, abs=1.0)
        assert r.shipping_cost.n_shipments_costed == 60

    def test_hand_computed_carrier_costs(self, main_df):
        """DHL Saudi: 14 shipments, total 945.00, avg 67.50 (independently
        verified via pandas groupby)."""
        r = analyze_logistics_intelligence(main_df)
        item = _item(r.shipping_cost.by_carrier, carrier="DHL Saudi")
        assert item.total_cost == pytest.approx(945.0, abs=0.5)
        assert item.avg_cost == pytest.approx(67.5, abs=0.1)
        assert item.n_shipments == 14

    def test_period_variance_computed_with_enough_history(self, main_df):
        """6 months of ship dates (2025-11 .. 2026-04) -> 5 consecutive
        period comparisons, reusing the established variance shape."""
        r = analyze_logistics_intelligence(main_df)
        assert len(r.shipping_cost.period_variances) == 5
        mags = [abs(v.cost_variance_pct or 0) for v in r.shipping_cost.period_variances]
        assert mags == sorted(mags, reverse=True)


# ── Section 4: Carrier / Route Performance (constructed heuristic) ─────────

class TestCarrierRoutePerformance:
    def test_marked_as_constructed_heuristic_not_validated(self, main_df):
        r = analyze_logistics_intelligence(main_df)
        assert r.carrier_route_performance.is_validated_instrument is False
        assert r.carrier_route_performance.confidence == "constructed_heuristic_not_validated"

    def test_hand_computed_dhl_best_delivery_worst_cost(self, main_df):
        """DHL Saudi: on-time 92.3% (best delivery), but avg cost 67.50 is
        the highest -> cost_component should be lowest among carriers."""
        r = analyze_logistics_intelligence(main_df)
        item = _item(r.carrier_route_performance.carrier_items, carrier="DHL Saudi")
        assert item.delivery_component == pytest.approx(92.3, abs=0.1)
        assert item.cost_component < 20  # far above the cheapest carrier's cost

    def test_hand_computed_aramex_cheapest_gets_full_cost_component(self, main_df):
        """Aramex has the lowest avg cost (35.75) among all 4 carriers ->
        cost_component = 100 (the cheapest-carrier baseline)."""
        r = analyze_logistics_intelligence(main_df)
        item = _item(r.carrier_route_performance.carrier_items, carrier="Aramex")
        assert item.cost_component == 100.0

    def test_route_breakdown_present(self, main_df):
        r = analyze_logistics_intelligence(main_df)
        routes = {i.route for i in r.carrier_route_performance.route_items}
        assert routes == {"Riyadh-Jeddah", "Jeddah-Makkah", "Dammam-Khobar", "Riyadh-Dammam"}

    def test_hand_computed_riyadh_dammam_worst_route(self, main_df):
        """Riyadh-Dammam (Fetchr's problem route) has the worst on-time %
        among all routes."""
        r = analyze_logistics_intelligence(main_df)
        item = _item(r.carrier_route_performance.route_items, route="Riyadh-Dammam")
        assert item.on_time_pct == pytest.approx(37.5, abs=0.5)


# ── Section 5: Delay Analysis ─────────────────────────────────────────────

class TestDelayAnalysis:
    def test_hand_computed_total_late(self, main_df):
        """12 late shipments total (actual>expected) out of 54 with
        complete dates."""
        r = analyze_logistics_intelligence(main_df)
        assert r.delay_analysis.available is True
        assert r.delay_analysis.n_late_total == 12

    def test_hand_computed_concentration_flag(self, main_df):
        """Fetchr Logistics x Riyadh-Dammam: 5 late shipments, avg 6.0 days
        late -- clears the 3-shipment floor -> flagged."""
        r = analyze_logistics_intelligence(main_df)
        item = _item(r.delay_analysis.by_carrier_route, group="Fetchr Logistics · Riyadh-Dammam")
        assert item.n_late == 5
        assert item.avg_days_late == pytest.approx(6.0, abs=0.1)
        assert item.is_concentration_flagged is True

    def test_below_floor_not_flagged_as_concentration(self, main_df):
        """DHL Saudi x Jeddah-Makkah: only 1 late shipment -- below the
        3-shipment floor -- must NOT be flagged as a concentration, even
        though the raw count is still reported."""
        r = analyze_logistics_intelligence(main_df)
        item = _item(r.delay_analysis.by_carrier_route, group="DHL Saudi · Jeddah-Makkah")
        assert item.n_late == 1
        assert item.is_concentration_flagged is False

    def test_min_late_threshold_disclosed(self, main_df):
        r = analyze_logistics_intelligence(main_df)
        assert r.delay_analysis.min_late_for_flag == 3

    def test_not_available_without_delivery_dates(self):
        df = pd.DataFrame({"Carrier": ["X"], "Status": ["Delayed"]})
        r = analyze_logistics_intelligence(df)
        assert r.delay_analysis.available is False


# ── Section 6: Returns Analysis (reuses Exit Interview's TF-IDF machinery) ─

class TestReturnsAnalysis:
    def test_hand_computed_return_rate(self, main_df):
        """11 of 60 shipments returned = 18.33%."""
        r = analyze_logistics_intelligence(main_df)
        assert r.returns_analysis.available is True
        assert r.returns_analysis.n_returned == 11
        assert r.returns_analysis.return_rate_pct == pytest.approx(18.33, abs=0.05)

    def test_hand_computed_themes_at_exactly_three_mentions(self, main_df):
        """Damaged in Transit, Wrong Item Shipped, and Defective Product
        each appear in exactly 3 of the 11 return reasons -- all three
        clear the >=3-distinct-shipments floor."""
        r = analyze_logistics_intelligence(main_df)
        themes = {t.theme: t.n_shipments_mentioned for t in r.returns_analysis.theme_frequencies}
        assert themes["Damaged in Transit"] == 3
        assert themes["Wrong Item Shipped"] == 3
        assert themes["Defective Product"] == 3

    def test_theme_below_floor_suppressed(self, main_df):
        """'Late Delivery' is only mentioned in 2 of the 11 reasons --
        below the 3-shipment floor -- must be suppressed, never shown."""
        r = analyze_logistics_intelligence(main_df)
        themes = {t.theme for t in r.returns_analysis.theme_frequencies}
        assert "Late Delivery" not in themes

    def test_min_mentions_threshold_matches_exit_interview(self, main_df):
        """Explicitly matches Exit Interview Intelligence's established
        MIN_DOCUMENT_FREQUENCY=3 threshold, per the brief."""
        r = analyze_logistics_intelligence(main_df)
        assert r.returns_analysis.min_mentions_for_theme == 3

    def test_no_raw_return_text_in_result(self, main_df):
        """Governance requirement: no raw return-reason text ever appears
        in the result, only aggregate theme counts and TF-IDF terms."""
        r = analyze_logistics_intelligence(main_df)
        raw_reasons = set(main_df["ReturnReason"].dropna())
        for term, _n in r.returns_analysis.top_terms:
            assert term not in raw_reasons
        assert "arrived damaged during transit" not in str(r.returns_analysis.theme_frequencies)


# ── Section 7: Cross-module honest degradation ──────────────────────────────

class TestCrossModuleDifferentiation:
    """Proves this module never accidentally computes anything from
    Procurement (Phase 33), Inventory (Phase 32), Financial (Phase 30), or
    Accounting (Phase 31) fixtures."""

    def test_unavailable_on_procurement_fixture(self):
        """Procurement's fixture has ExpectedDeliveryDate/ActualDeliveryDate
        columns that superficially match this module's date patterns too,
        but lacks carrier/route/status/cost entirely -- the per-row
        shipment-building guard must exclude every row regardless, so ALL
        SIX items stay unavailable, not just the ones needing carrier/cost."""
        df = pd.read_csv("procurement_transactions_test_data.csv")
        r = analyze_logistics_intelligence(df)
        assert r.shipment_status.available is False
        assert r.delivery_time.available is False
        assert r.shipping_cost.available is False
        assert r.carrier_route_performance.available is False
        assert r.delay_analysis.available is False
        assert r.returns_analysis.available is False

    def test_unavailable_on_inventory_fixture(self):
        df = pd.read_csv("inventory_transactions_test_data.csv")
        r = analyze_logistics_intelligence(df)
        assert r.shipment_status.available is False

    def test_unavailable_on_employee_data(self):
        df = pd.read_csv("test_employee_data.csv")
        r = analyze_logistics_intelligence(df)
        assert r.shipment_status.available is False

    def test_never_fabricates_on_empty_data(self):
        r = analyze_logistics_intelligence(pd.DataFrame())
        assert r.shipment_status.available is False
        assert r.delivery_time.available is False
        assert r.shipping_cost.available is False
        assert r.carrier_route_performance.available is False
        assert r.delay_analysis.available is False
        assert r.returns_analysis.available is False


# ── Section 8: Bundle + serialization sanity ────────────────────────────────

class TestBundleAndSerialization:
    def test_analyze_bundles_all_six(self, main_df):
        r = analyze_logistics_intelligence(main_df)
        assert r.shipment_status.available is True
        assert r.delivery_time.available is True
        assert r.shipping_cost.available is True
        assert r.carrier_route_performance.available is True
        assert r.delay_analysis.available is True
        assert r.returns_analysis.available is True

    def test_to_dict_contains_all_sections(self, main_df):
        from backend.core.logistics_intelligence_engine import logistics_intelligence_to_dict
        r = analyze_logistics_intelligence(main_df)
        d = logistics_intelligence_to_dict(r)
        for key in ["shipment_status", "delivery_time", "shipping_cost", "carrier_route_performance", "delay_analysis", "returns_analysis", "disclaimer_en", "disclaimer_ar", "sources"]:
            assert key in d

    def test_never_raises_on_malformed_input(self):
        df = pd.DataFrame({"Carrier": [None, None], "Status": ["x", "y"], "Cost": ["a", "b"]})
        r = analyze_logistics_intelligence(df)
        assert isinstance(r.shipment_status.available, bool)
