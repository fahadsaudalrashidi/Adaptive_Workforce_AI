# Phase 32 — Inventory Intelligence Phase 1 (Business Intelligence Suite, Module 3)

Inventory Intelligence is the platform's fourth genuinely distinct data shape (item-level stock/
transaction data) and third Business Intelligence module — kept fully separate from
`financial_intelligence_reporting_engine.py` (Phase 30) and `accounting_intelligence_engine.py`
(Phase 31), with no shared imports or column-pattern constants between the three.

---

## 1. Upload Shape Designed

Two supported shapes, detected independently, never assumed:

| Shape | Columns | What it activates |
|---|---|---|
| **Snapshot** | SKU + QuantityOnHand + UnitCost (+ optional Category) | Only items 1 (Stock Levels) and 4 (ABC Analysis) — both need only a point-in-time quantity × cost |
| **Transaction log** | SKU + TransactionDate + TransactionType (Receipt/Issue) + QuantityMoved + UnitCost (+ optional Category, LeadTimeDays, Warehouse) | All 6 items; current stock is **derived** as net(receipts − issues) per SKU, disclosed via `current_stock_source: "derived_from_movement"` |

A single upload may contain both (a richer export) — `QuantityOnHand` is then used directly as the
more authoritative "current stock" source while movement history still powers every
movement-dependent computation. Lead time (`LeadTimeDays`) is evaluated **per SKU**, so a single
upload can mix items with and without real lead-time data — proven in the fixture (4 of 13 SKUs
have lead times, 9 don't).

Column detection: `backend/core/inventory_intelligence_engine.py:78-134` (SKU, item name,
category, quantity-on-hand, unit cost, transaction date, transaction type, quantity moved,
warehouse, lead time — fuzzy EN+AR local-regex, fresh to this module).

---

## 2. The 6 Items Built — Formula Choices and Honest Degradation

All in `backend/core/inventory_intelligence_engine.py` (1,064 lines).

| # | Item | Formula used | Honest-degradation behavior |
|---|---|---|---|
| 1 | **Current Stock Levels & Movement** (`_stock_levels_from_items`, line ~410) | `current_stock` = QuantityOnHand column if present, else net(receipts − issues) from real transactions | If no movement history exists, narrative explicitly states "only a point-in-time snapshot is available — no movement trend can be shown," same discipline as Payroll Movements' `data_mode` |
| 2 | **Inventory Turnover** (`_turnover_from_items`, line ~525) | `cogs_over_avg_inventory_value` (COGS issued ÷ average inventory value, using a full daily-resampled running-balance series, not a crude 2-point average) when unit cost present; `units_moved_over_avg_units_on_hand` when it isn't — the two are explicitly disclosed as non-interchangeable | Unavailable without real movement history — a snapshot alone cannot support it |
| 3 | **Dead Stock / Slow-Moving / Stock Aging** (`_aging_from_items`, line ~597) | Documented tiers: active (≤30d) / watch (31-90d) / slow_moving (91-180d) / dead_stock (180+d) since last movement — mirrors `contract_expiry_engine.py`'s disclosed-threshold honesty | Unavailable without real transaction dates |
| 4 | **ABC Analysis** (`_abc_from_items`, line ~677) | Standard 80/15/5 cumulative-value Pareto convention, cited as a disclosed choice (not the only textbook variant) | **Computable from a snapshot alone** — needs only quantity × cost, no movement required |
| 5 | **Reorder Point & Safety Stock** (`_reorder_points_from_items`, line ~770) | Per-SKU: `lead_time_variability` (SS = Z·σ·√LeadTime, Z=1.65; ROP = avg_demand·LeadTime + SS) when a real lead time exists; `average_demand_days_of_supply` (reports avg daily demand + days-of-supply remaining instead of an absolute reorder point) when it doesn't — never fabricates a lead-time assumption | Unavailable without real movement history at all |
| 6 | **Overstock & Stockout Risk** (`_overstock_stockout_from_reorder`, line ~893) | Filters item 5's own `ReorderPointItem` list (`stockout_risk`/`overstock` booleans computed once, inside item 5) — verified by test `test_items_reused_from_reorder_points_not_recomputed` that the exact same figures appear in both places | Mirrors item 5's availability exactly — never computed separately |

---

## 3. Fixture Design

`inventory_transactions_test_data.csv` (repo root, 81 rows / 13 SKUs, 2025-10-01 to 2026-04-20,
`as_of_date=2026-04-30`) — built via a scratch script, cross-verified with pandas
(`.quantile()`, daily-resampled running balance, `groupby`) before any test was written:

- **Dead/slow-moving cases**: CONNECTOR-X12 (206 days), VALVE-ASSY (203 days), CONVEYOR-10M
  (198 days) → `dead_stock`; FILTER-AIR (105 days) → `slow_moving`; MOTOR-5HP (36 days) → `watch`.
- **ABC value spread**: total inventory value SAR 76,376.75 across 13 SKUs, from SAR 180.00
  (TAPE-ROLL) to SAR 24,150.00 (VALVE-ASSY) — a genuine 5/4/4 A/B/C split, not manufactured to hit
  round numbers.
- **Stockout case**: TAPE-ROLL — high daily demand (24.167 units/day) against low current stock
  (150 units) and a real 5-day lead time → safety stock 442.28 > current stock → flagged.
- **Overstock cases**: 8 of 13 items, spanning both formula paths — HELMET and PUMP-HP200 (real
  lead time, current stock far exceeds computed reorder point) and 6 more via the days-of-supply
  fallback (BEARING-6205, CONNECTOR-X12, CONVEYOR-10M, FILTER-AIR, MOTOR-5HP, VALVE-ASSY). This
  is a genuine, not manufactured, characteristic of the fixture — most items carry more stock than
  their computed reorder point suggests is needed, a realistic finding for a first inventory
  review, not a fixture defect.
- **Mixed lead-time availability**: 4 SKUs (BOLT-M8, HELMET, PUMP-HP200, TAPE-ROLL) carry real
  `LeadTimeDays`; the other 9 don't — proving both reorder-point formulas render side by side from
  one upload.

`inventory_snapshot_only_test_data.csv` (13 rows) — the same 13 SKUs' current stock and unit cost
with **no** transaction/date/type columns at all, built by aggregating the main fixture's net
movements into a pure point-in-time export — used to prove the snapshot-vs-history degradation.

---

## 4. Test Results

**New tests**: `tests/test_inventory_intelligence_engine.py` — 30/30 passing, organized into 8
sections covering all 6 items' hand-computed figures (Stock Levels, Turnover, Stock Aging, ABC,
Reorder Points, Overstock/Stockout), cross-module honest degradation against Phase 30/31's
fixtures and a real employee CSV, and bundle/serialization sanity.

**Full regression suite**: `1694 passed, 1 skipped, 1 failed` (the same pre-existing, unrelated
`test_health_wheel_imported` failure present before this phase — 1664 baseline + 30 new tests =
1694). **Zero regressions introduced.**

---

## 5. Live Browser Verification

Playwright run against the live backend + Vite dev server. Zero console/page errors
(`CONSOLE_ERRORS: []`).

| Screenshot | Confirmed |
|---|---|
| Stock Levels tab | 13 items, "Movement History: Available"; BOLT-M8 current stock 2,290.00 (derived) — exact match |
| Turnover tab | Formula banner correctly states COGS/avg-inventory-value; BOLT-M8 avg inventory value SAR 2,634.94, turnover 1.653 — exact match |
| Stock Aging tab | Tier counts 8/1/1/3 (active/watch/slow-moving/dead stock); CONNECTOR-X12/VALVE-ASSY/CONVEYOR-10M at 206/203/198 days — exact match |
| ABC Analysis tab | Total value SAR 76,376.75; tier counts 5/4/4 (82.8%/12.8%/4.4% of value); VALVE-ASSY ranked #1 at SAR 24,150.00 — exact match |
| Reorder Point tab | TAPE-ROLL: safety stock 442.28 / reorder point 563.11, flagged Stockout; VALVE-ASSY: 4,830.0 days of supply, flagged Overstock; both formula paths rendered side by side — exact match |
| Overstock & Stockout tab | 1 stockout (TAPE-ROLL) / 8 overstock, banner states figures are reused from Reorder Point, not recomputed — exact match |
| Snapshot-only: ABC tab | Identical ABC output (5/4/4, SAR 76,376.75) computed from a file with zero movement columns — proves item 4 needs no history |
| Snapshot-only: Turnover tab | "Inventory turnover not computable from this upload" — Transaction date/type/quantity-moved correctly shown as missing while SKU/UnitCost show detected |
| Cross-module: Reorder Point tab on Phase 31's GL fixture | "Reorder point not computable... No SKU/item-code column detected" — correctly unavailable despite the GL file's generic "Description"/"EntryDate" columns incidentally fuzzy-matching Item-Name/Date patterns (noted below) |

**A fuzzy-matching nuance found during verification, not a bug**: uploading Phase 31's GL fixture
shows "Item name" and "Transaction date" as green/detected in the honest-degradation checklist,
because that file's generic `Description` and `EntryDate` columns incidentally match this module's
deliberately broad fuzzy patterns. This never causes a false "available" result — the module still
correctly reports `available: false` because the master gate (`SKU` column, or a complete
movement-column set) isn't met — but it's worth noting that individual checklist items can light up
from incidental name overlap across domains without the section becoming computable. Documented
here for transparency rather than tightened, since over-narrowing the patterns risks missing real
inventory files with differently-worded date/description columns.

---

## 6. Phase 2 Backlog

- **Demand forecasting** — deferred, as specified.
- **Waste/damage analysis** — deferred, as specified.
- **Multi-warehouse comparison** — the `Warehouse` column is detected (`_WAREHOUSE_PATTERNS`,
  line 122) and captured in the fixture, but no warehouse-level rollup or comparison was built this
  phase — deferred, as specified.
- **Inventory carrying-cost analysis — ownership question flagged, not built**: this could belong
  to either Inventory Intelligence (it's a stock-holding cost) or Financial Intelligence (it's
  fundamentally a cost-of-capital / financial calculation applied to inventory value). Building it
  in one module risks silently duplicating it in the other later. Recommend deciding ownership
  explicitly before Phase 2 rather than defaulting to either.
- **Anything requiring purchase-order data** (PO-to-receipt matching, supplier lead-time actuals
  vs. quoted, PO aging) — explicitly belongs to the upcoming Procurement Intelligence phase, not
  Inventory. Not built here.

---

## Regression Count

**1694 passed, 1 skipped, 1 pre-existing unrelated failure. Zero regressions.**

## Environment Note

Same dev-environment ghost-socket condition as Phases 30-31 (`127.0.0.1:8000` stale TCP entry);
`executive-ui/vite.config.ts`'s proxy target (already pointed at the LAN IP since Phase 31) was
reused unchanged — no further config change needed this phase.
