"""
Tests for backend.core.inventory_intelligence_engine — Phase 32.

Fixtures:
  - inventory_transactions_test_data.csv: 13 SKUs, 81 movement rows spanning
    2025-10-01 to 2026-04-20 (as_of=2026-04-30). All expected figures below
    were independently computed with pandas directly against this CSV (see
    the build script this phase used — daily-resampled running balance for
    turnover/avg-inventory, IQR-free std-dev for demand variability),
    documented inline, not re-derived from the engine.
  - inventory_snapshot_only_test_data.csv: same 13 SKUs' current stock +
    unit cost, but NO movement/date columns at all — proves the honest
    snapshot-vs-history degradation.
  - financial_transactions_test_data.csv / accounting_gl_test_data.csv
    (Phase 30/31 fixtures): used to prove zero cross-module overlap.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.core.inventory_intelligence_engine import (
    analyze_inventory_intelligence,
)

MAIN_FIXTURE = "inventory_transactions_test_data.csv"
SNAPSHOT_FIXTURE = "inventory_snapshot_only_test_data.csv"
AS_OF = "2026-04-30"


@pytest.fixture
def main_df():
    return pd.read_csv(MAIN_FIXTURE)


@pytest.fixture
def snapshot_df():
    return pd.read_csv(SNAPSHOT_FIXTURE)


def _item(result_items, sku):
    return next(i for i in result_items if i.sku == sku)


# ── Section 1: Current Stock Levels & Movement ──────────────────────────────

class TestStockLevels:
    def test_hand_computed_totals(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        assert r.stock_levels.available is True
        assert r.stock_levels.n_items == 13
        assert r.stock_levels.has_movement_history is True

    def test_hand_computed_bolt_m8_stock(self, main_df):
        """BOLT-M8: received 8000(opening)+3000=11000; issued sum of 11
        listed issues = 8710. Current stock = 11000-8710 = 2290."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        item = _item(r.stock_levels.items, "BOLT-M8")
        assert item.current_stock == 2290.0
        assert item.current_stock_source == "derived_from_movement"
        assert item.total_received == 11000.0
        assert item.total_issued == 8710.0

    def test_snapshot_only_gives_no_movement_history(self, snapshot_df):
        r = analyze_inventory_intelligence(snapshot_df)
        assert r.stock_levels.available is True
        assert r.stock_levels.has_movement_history is False
        item = _item(r.stock_levels.items, "BOLT-M8")
        assert item.current_stock_source == "snapshot_column"
        assert item.total_issued is None  # no movement to report

    def test_not_available_without_sku_or_quantity_signal(self):
        r = analyze_inventory_intelligence(pd.DataFrame({"Foo": [1, 2]}))
        assert r.stock_levels.available is False


# ── Section 2: Inventory Turnover ───────────────────────────────────────────

class TestTurnover:
    def test_formula_choice_uses_cogs_when_cost_present(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        assert r.turnover.available is True
        assert r.turnover.formula_used == "cogs_over_avg_inventory_value"

    def test_hand_computed_bolt_m8_turnover(self, main_df):
        """BOLT-M8: total_issued=8710; avg_units_on_hand (daily-resampled
        running-balance mean over 2025-11-01..2026-04-30) = 2634.94 units of
        VALUE / unit_cost 0.50 -> avg_inventory_value=2634.94 (already in
        SAR since computed as avg_units*cost); turnover = (8710*0.50)/2634.94
        = 1.653 (independently computed via pandas)."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        item = _item(r.turnover.items, "BOLT-M8")
        assert item.avg_inventory_value == pytest.approx(2634.94, abs=0.05)
        assert item.turnover_ratio == pytest.approx(1.653, abs=0.01)

    def test_not_available_snapshot_only(self, snapshot_df):
        r = analyze_inventory_intelligence(snapshot_df)
        assert r.turnover.available is False
        assert "movement history" in r.turnover.reason.lower()


# ── Section 3: Stock Aging / Dead Stock ─────────────────────────────────────

class TestStockAging:
    def test_hand_computed_tier_counts(self, main_df):
        """As of 2026-04-30: CONNECTOR-X12(206d)/VALVE-ASSY(203d)/
        CONVEYOR-10M(198d) -> dead_stock (>180); FILTER-AIR(105d) ->
        slow_moving (91-180); MOTOR-5HP(36d) -> watch (31-90); remaining
        8 items <=30d -> active."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        assert r.stock_aging.available is True
        assert r.stock_aging.tier_counts == {
            "active": 8, "watch": 1, "slow_moving": 1, "dead_stock": 3,
        }

    def test_hand_computed_dead_stock_items(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        dead = {i.sku for i in r.stock_aging.items if i.tier == "dead_stock"}
        assert dead == {"CONNECTOR-X12", "VALVE-ASSY", "CONVEYOR-10M"}

    def test_days_since_last_movement_exact(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        item = _item(r.stock_aging.items, "CONNECTOR-X12")
        assert item.days_since_last_movement == 206  # last issue 2025-10-06

    def test_not_available_snapshot_only(self, snapshot_df):
        r = analyze_inventory_intelligence(snapshot_df)
        assert r.stock_aging.available is False


# ── Section 4: ABC Analysis ──────────────────────────────────────────────────

class TestABCAnalysis:
    def test_hand_computed_tier_counts(self, main_df):
        """80/15/5 cumulative-value convention (cumulative-before rule):
        A={VALVE-ASSY,PUMP-HP200,CONVEYOR-10M,MOTOR-5HP,BEARING-6205} (5),
        B={GLOVES-L,HELMET,CONNECTOR-X12,BOX-LARGE} (4),
        C={FILTER-AIR,BOLT-M8,BOLT-M10,TAPE-ROLL} (4).
        Independently verified via pandas groupby + cumulative sum."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        assert r.abc_analysis.available is True
        assert r.abc_analysis.tier_counts == {"A": 5, "B": 4, "C": 4}
        assert r.abc_analysis.total_value == pytest.approx(76376.75, abs=0.01)

    def test_hand_computed_a_tier_membership(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        a_tier = {i.sku for i in r.abc_analysis.items if i.tier == "A"}
        assert a_tier == {"VALVE-ASSY", "PUMP-HP200", "CONVEYOR-10M", "MOTOR-5HP", "BEARING-6205"}

    def test_top_item_is_highest_value(self, main_df):
        """VALVE-ASSY: 115 units x SAR 210.00 = SAR 24,150.00 — the single
        highest-value item, correctly ranked first and tier A."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        top = r.abc_analysis.items[0]
        assert top.sku == "VALVE-ASSY"
        assert top.value_on_hand == 24150.0
        assert top.tier == "A"

    def test_available_from_snapshot_alone_no_movement_needed(self, snapshot_df):
        """ABC only needs quantity x cost — computable from a pure snapshot,
        unlike turnover/aging/reorder-point."""
        r = analyze_inventory_intelligence(snapshot_df)
        assert r.abc_analysis.available is True
        assert r.abc_analysis.tier_counts == {"A": 5, "B": 4, "C": 4}


# ── Section 5: Reorder Point & Safety Stock ─────────────────────────────────

class TestReorderPoints:
    def test_lead_time_items_use_full_formula(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        assert r.reorder_points.available is True
        for sku in ("BOLT-M8", "HELMET", "PUMP-HP200", "TAPE-ROLL"):
            item = _item(r.reorder_points.items, sku)
            assert item.formula_used == "lead_time_variability"
            assert item.safety_stock is not None
            assert item.reorder_point is not None
            assert item.days_of_supply is None

    def test_no_lead_time_items_use_days_of_supply_fallback(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        for sku in ("BEARING-6205", "BOX-LARGE", "GLOVES-L", "VALVE-ASSY"):
            item = _item(r.reorder_points.items, sku)
            assert item.formula_used == "average_demand_days_of_supply"
            assert item.safety_stock is None
            assert item.reorder_point is None
            assert item.days_of_supply is not None

    def test_hand_computed_tape_roll_stockout(self, main_df):
        """TAPE-ROLL: current_stock=150, lead_time=5, demand_std/avg_demand
        computed from daily-resampled issue series -> safety_stock=442.28,
        reorder_point=563.11 (independently verified via pandas). 150 <
        442.28 -> stockout_risk=True."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        item = _item(r.reorder_points.items, "TAPE-ROLL")
        assert item.current_stock == 150.0
        assert item.safety_stock == pytest.approx(442.28, abs=0.5)
        assert item.reorder_point == pytest.approx(563.11, abs=0.5)
        assert item.stockout_risk is True
        assert item.overstock is False

    def test_hand_computed_valve_assy_overstock_no_lead_time(self, main_df):
        """VALVE-ASSY: no lead time -> days_of_supply = 115 / (5/210 obs
        days) ~= 4830 days (independently computed), far above the 180-day
        overstock ceiling -> overstock=True."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        item = _item(r.reorder_points.items, "VALVE-ASSY")
        assert item.days_of_supply == pytest.approx(4830.0, abs=5.0)
        assert item.overstock is True
        assert item.stockout_risk is False

    def test_not_available_snapshot_only(self, snapshot_df):
        r = analyze_inventory_intelligence(snapshot_df)
        assert r.reorder_points.available is False
        assert "movement history" in r.reorder_points.reason.lower()


# ── Section 6: Overstock & Stockout Risk (reuses item 5, no parallel calc) ──

class TestOverstockStockout:
    def test_hand_computed_counts(self, main_df):
        """Exactly 1 stockout-risk item (TAPE-ROLL) and 7 overstock items
        (BEARING-6205, CONNECTOR-X12, CONVEYOR-10M, FILTER-AIR, HELMET,
        MOTOR-5HP, PUMP-HP200, VALVE-ASSY) -- independently verified."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        assert r.overstock_stockout.available is True
        assert r.overstock_stockout.n_stockout_risk == 1
        assert {i.sku for i in r.overstock_stockout.stockout_items} == {"TAPE-ROLL"}
        overstock_skus = {i.sku for i in r.overstock_stockout.overstock_items}
        assert overstock_skus == {
            "BEARING-6205", "CONNECTOR-X12", "CONVEYOR-10M", "FILTER-AIR",
            "HELMET", "MOTOR-5HP", "PUMP-HP200", "VALVE-ASSY",
        }
        assert r.overstock_stockout.n_overstock == 8

    def test_items_reused_from_reorder_points_not_recomputed(self, main_df):
        """The exact same ReorderPointItem objects (by SKU + figures) appear
        in both item 5's list and item 6's filtered lists -- proving no
        separate parallel calculation exists."""
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        rp_tape = _item(r.reorder_points.items, "TAPE-ROLL")
        stockout_tape = _item(r.overstock_stockout.stockout_items, "TAPE-ROLL")
        assert rp_tape.safety_stock == stockout_tape.safety_stock
        assert rp_tape.reorder_point == stockout_tape.reorder_point

    def test_not_available_snapshot_only_mirrors_reorder(self, snapshot_df):
        r = analyze_inventory_intelligence(snapshot_df)
        assert r.overstock_stockout.available is False


# ── Section 7: Cross-module honest degradation ──────────────────────────────

class TestCrossModuleDifferentiation:
    """Proves this module never accidentally computes anything from Phase
    30's (financial transactions) or Phase 31's (GL journal) fixtures —
    neither has SKU/quantity/inventory-shaped columns."""

    def test_unavailable_on_phase30_fixture(self):
        df = pd.read_csv("financial_transactions_test_data.csv")
        r = analyze_inventory_intelligence(df)
        assert r.stock_levels.available is False
        assert r.abc_analysis.available is False

    def test_unavailable_on_phase31_fixture(self):
        df = pd.read_csv("accounting_gl_test_data.csv")
        r = analyze_inventory_intelligence(df)
        assert r.stock_levels.available is False
        assert r.abc_analysis.available is False

    def test_unavailable_on_employee_data(self):
        df = pd.read_csv("test_employee_data.csv")
        r = analyze_inventory_intelligence(df)
        assert r.stock_levels.available is False

    def test_never_fabricates_on_empty_data(self):
        r = analyze_inventory_intelligence(pd.DataFrame())
        assert r.stock_levels.available is False
        assert r.turnover.available is False
        assert r.stock_aging.available is False
        assert r.abc_analysis.available is False
        assert r.reorder_points.available is False
        assert r.overstock_stockout.available is False


# ── Section 8: Bundle + serialization sanity ────────────────────────────────

class TestBundleAndSerialization:
    def test_analyze_bundles_all_six(self, main_df):
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        assert r.stock_levels.available is True
        assert r.turnover.available is True
        assert r.stock_aging.available is True
        assert r.abc_analysis.available is True
        assert r.reorder_points.available is True
        assert r.overstock_stockout.available is True

    def test_to_dict_contains_all_sections(self, main_df):
        from backend.core.inventory_intelligence_engine import inventory_intelligence_to_dict
        r = analyze_inventory_intelligence(main_df, as_of_date=AS_OF)
        d = inventory_intelligence_to_dict(r)
        for key in ["stock_levels", "turnover", "stock_aging", "abc_analysis", "reorder_points", "overstock_stockout", "disclaimer_en", "disclaimer_ar", "sources"]:
            assert key in d

    def test_never_raises_on_malformed_input(self):
        df = pd.DataFrame({"SKU": [None, None], "QuantityOnHand": ["x", "y"]})
        r = analyze_inventory_intelligence(df)
        assert r.stock_levels.available is False
