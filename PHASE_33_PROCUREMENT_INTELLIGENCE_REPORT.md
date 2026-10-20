# Phase 33 — Procurement Intelligence Phase 1 (Business Intelligence Suite, Module 4)

Procurement Intelligence is the platform's fourth Business Intelligence module: purchase-order/
supplier-level data. Related to Inventory Intelligence (Phase 32, which tracks stock ON HAND) but
distinct — this module tracks the BUYING PROCESS and supplier relationships that replenish it.
Kept as a fully separate engine (`backend/core/procurement_intelligence_engine.py`), no shared
imports with `inventory_intelligence_engine.py`.

---

## 1. Upload Shape Designed

One purchase-order-line-per-row shape, fuzzy-detected (EN+AR local-regex,
`backend/core/procurement_intelligence_engine.py:84-133`):

| Field | Required? | Notes |
|---|---|---|
| Supplier name/ID | **required** | Master key for 5 of 6 items |
| SKU/item code | **required** | Master key for all 6 items |
| Item name | optional | |
| Category | optional | Enables spend-by-category rollup |
| PO/order date | required for items 2 (drill-down chronology), 3, 4 | |
| Unit price | required unless a direct total-spend column exists | |
| Quantity | required unless a direct total-spend column exists | |
| Total spend | optional direct column — derived from `unit_price × quantity` when absent, disclosed via `spend_source` | |
| Expected delivery date | optional, evaluated **per supplier** | |
| Actual delivery date | optional, evaluated **per supplier** | |

Delivery-date honesty is per-supplier, not just per-file: a single upload can have complete
delivery data for some suppliers and none for others (proven live — Riyadh Industrial Supplies has
zero delivery-date rows while the other 4 suppliers have real on-time percentages).

---

## 2. The 6 Items Built — Methodology and Honest Degradation

All in `backend/core/procurement_intelligence_engine.py` (1,022 lines).

| # | Item | Methodology | Honest-degradation behavior |
|---|---|---|---|
| 1 | **Supplier Spend Analysis** (`_supplier_spend_from_lines`, line 348) | Sum of spend (direct column or price×qty) per supplier, plus per-category breakdown | Unavailable without a computable spend signal on any row |
| 2 | **PO & Price Analysis** (`_po_price_from_lines`, line 427) | Chronological price-point drill-down per (supplier, SKU) pair — avg/min/max plus every individual PO | Unavailable without a unit-price column |
| 3 | **Price Variance / Trend Tracking** (`_price_trend_from_lines`, line 511) | Monthly period bucketing, `variance = current − prior`, `variance_pct = round(100·variance/prior, 2)`, sorted by absolute magnitude — the exact shape already established in `payroll_budget_engine.py`/Phase 30/31's variance dataclasses | Gated on `_MIN_PERIODS_FOR_TREND=2` **and** `_MIN_POS_FOR_TREND=4` per (supplier, SKU) pair — pairs below the floor are counted and disclosed as suppressed, never guessed from a 2-point comparison |
| 4 | **Delivery/On-Time Performance** (`_delivery_from_lines`, line 609) | `on_time = actual_delivery ≤ expected_delivery`; `on_time_pct` per supplier from rows with both dates present | Suppliers with zero rows carrying both dates are listed separately (`suppliers_without_delivery_data`), never defaulted to any percentage |
| 5 | **Supplier Performance Scoring** (`_performance_from_components`, line 687) | Constructed heuristic: `composite = 0.5·delivery_on_time_pct + 0.5·price_trend_component` when both available, or the single available component alone; `price_trend_component = 100 − max(0, avg_eligible_price_increase_pct)`, built only from item 3's **eligible** (non-suppressed) pairs | Explicitly marked `is_validated_instrument=False`, `confidence="constructed_heuristic_not_validated"` (same framing as `succession_readiness_engine.py`). Suppliers with **zero** computable components are excluded from scoring entirely, never force-scored — verified by test and live screenshot (Riyadh) |
| 6 | **Cost-Reduction Opportunity Flagging** (`_cost_reduction_from_lines`, line 791) | For each SKU sourced from ≥2 suppliers, compares real average price per supplier; flags when `(max_avg − min_avg)/min_avg ≥ _COST_REDUCTION_THRESHOLD_PCT` (8%, disclosed) | Single-supplier items never compared (nothing to flag); each flagged item discloses the real PO count backing each supplier's average, so confidence is visible, not hidden |

A bug caught and fixed during smoke-testing (not just in the live UI): the initial
`n_suppliers_excluded_no_data` counter in item 5 only counted suppliers that appeared in at least
one of the two partial component maps — a supplier with **neither** delivery data nor an eligible
price trend (Riyadh, in the fixture) never entered either map and was silently undercounted.
Fixed by passing the full set of suppliers actually present in the uploaded data into the scoring
function, so the exclusion count is now accurate (verified: `n_suppliers_excluded_no_data == 1`,
matching Riyadh being the only fully-unscoreable supplier).

---

## 3. Fixture Design

`procurement_transactions_test_data.csv` (repo root, 40 PO lines, 5 suppliers, 8 SKUs, 2025-11 to
2026-03) — built via a scratch script, cross-verified with pandas before any test was written:

- **Cost-reduction cases (item 6)**: BOLT-M8 from Al-Rajhi Steel Supply (avg SAR 0.45, n=5) vs.
  Gulf Hardware Trading (avg SAR 0.55, n=3) → +22.22%; MOTOR-5HP from Precision Machinery Parts
  (avg SAR 432.33, n=3) vs. Riyadh Industrial Supplies (avg SAR 472.50, n=2) → +9.29%. Both clear
  the 8% threshold.
- **Price-trend cases (item 3)**: HELMET (Gulf Hardware Trading) rises 14.00→16.80 over 5 monthly
  POs (+20.00%, clearly eligible); GLOVES-L (National Safety Equipment Co) declines 3.60→3.40 over
  5 monthly POs (−5.56%, a favorable trend, proving the module isn't just tuned to detect
  increases). PUMP-HP200 (Precision Machinery Parts) has only 2 POs total → deliberately below the
  4-PO floor, suppressed.
- **Delivery-performance spread (item 4)**: on-time percentages deliberately varied — Al-Rajhi
  81.2%, National Safety Equipment Co 44.4%, Gulf Hardware Trading 25.0%, Precision Machinery
  Parts 0.0% (all 5 of its tracked deliveries were late). Riyadh Industrial Supplies has **no**
  delivery-date columns populated at all — the dedicated per-supplier honest-degradation case.
- **Performance-scoring edge cases (item 5)**: Al-Rajhi/National/Gulf all get both components;
  Precision gets delivery-only (its price trends are both suppressed); Riyadh gets **neither** and
  is excluded from scoring entirely.

---

## 4. Test Results

**New tests**: `tests/test_procurement_intelligence_engine.py` — 30/30 passing, organized into 8
sections covering all 6 items' hand-computed figures, cross-module honest degradation against
Inventory/Financial/Accounting fixtures and a real employee CSV, and bundle/serialization sanity.

**Full regression suite**: `1724 passed, 1 skipped, 1 failed` (the same pre-existing, unrelated
`test_health_wheel_imported` failure present before this phase — 1694 baseline + 30 new tests =
1724). **Zero regressions introduced.**

---

## 5. Live Browser Verification

Playwright run against the live backend + Vite dev server. Zero console/page errors
(`CONSOLE_ERRORS: []`).

| Screenshot | Confirmed |
|---|---|
| Supplier Spend tab | Total SAR 62,282.10 across 5 suppliers/40 POs; per-supplier totals and category breakdowns — exact match |
| Price Trend tab | HELMET +20.00% over 5 periods, GLOVES-L −5.56%, BOLT-M8 +2.27%; suppression banner states 4 pairs suppressed for insufficient sample — exact match |
| Delivery tab | 81.2% / 44.4% / 25.0% / 0.0% on-time by supplier; caution banner names Riyadh Industrial Supplies as having no delivery data at all — exact match |
| Supplier Score tab | Prominent "CONSTRUCTED HEURISTIC... NOT a validated... rating" disclaimer; Al-Rajhi 89.8, National 71.8, Gulf 52.5, Precision 0.0 (delivery-only); "1 supplier(s) excluded" banner — exact match |
| Cost Reduction tab | Both flagged opportunities (BOLT-M8 +22.2%, MOTOR-5HP +9.3%) with cheapest/priciest supplier, price, and real PO count shown for each side — exact match |
| Cross-module: uploading Inventory's fixture | "Cost-reduction flagging not available... No supplier and/or SKU/item-code column detected" — correctly unavailable (Inventory's fixture has an SKU column but no Supplier column) |

---

## 6. Phase 2 Backlog

- **Supplier risk scoring beyond the performance composite** — explicitly deferred, as specified.
  True risk scoring needs external data (financial health, credit ratings) this platform cannot
  access; building a "risk score" from only spend/delivery/price data would overstate what's
  actually knowable.
- **Live external market-price comparison** — explicitly deferred, as specified. This platform has
  no live market-price search capability (ruled out earlier this session); item 6's cost-reduction
  flagging is scoped specifically to avoid needing it, comparing only the user's own real
  multi-supplier data.

No other items from the requested scope remain outstanding — all 6 were built this phase.

---

## Regression Count

**1724 passed, 1 skipped, 1 pre-existing unrelated failure. Zero regressions.**

## Environment Note

Same dev-environment ghost-socket condition as Phases 30-32; `executive-ui/vite.config.ts`'s
proxy target (pointed at the LAN IP since Phase 31) was reused unchanged.
