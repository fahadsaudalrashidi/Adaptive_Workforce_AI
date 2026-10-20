# Phase 34 — Logistics Intelligence Phase 1 (Business Intelligence Suite, Module 5)

Logistics Intelligence is the platform's fifth Business Intelligence module: shipment/delivery-
level data. Related to Procurement Intelligence's delivery-performance item (Phase 33) but a
genuinely different focus — Procurement measures whether a *supplier* delivered inbound goods on
time; Logistics measures the platform owner's own *outbound* shipping performance to their
customers, carrier reliability, shipping cost, and returns.

---

## 1. Upload Shape Designed

One shipment-per-row shape, fuzzy-detected (EN+AR local-regex,
`backend/core/logistics_intelligence_engine.py:85-138`):

| Field | Required? | Notes |
|---|---|---|
| Shipment/order ID | optional | |
| Carrier | required for carrier-level views (items 3's per-carrier breakdown, item 4) | |
| Route (or Origin+Destination combo) | optional | Falls back to combining separate Origin/Destination columns as `"Origin → Destination"` if no single Route column exists |
| Ship date | required for the cost-trend view | |
| Expected delivery date | required for on-time/delay views | |
| Actual delivery date | required for on-time/delay views | |
| Status | required for the status overview (item 1) and returns rate (item 6) | Classified into delivered/in_transit/delayed/returned via a token classifier — unclassifiable values counted, never guessed |
| Cost | required for cost views | |
| Return flag | optional | Alternative signal to a `Status="Returned"` value |
| Return reason | optional, free text | Enables item 6's theme extraction |
| Delay reason/cause | optional, free text | Detected but not yet used in Phase 1 — see backlog |

A per-row guard requires at least one of {carrier, route, status, cost} before a row is treated as
a usable shipment record — this is what correctly excludes Procurement's fixture even though its
`ExpectedDeliveryDate`/`ActualDeliveryDate` columns superficially match Logistics' date patterns
too (see §6 below).

---

## 2. The 6 Items Built — Methodology and Honest Degradation

All in `backend/core/logistics_intelligence_engine.py` (1,109 lines).

| # | Item | Methodology | Honest-degradation behavior |
|---|---|---|---|
| 1 | **Shipment Volume & Status Overview** (`_status_overview_from_shipments`, line 360) | Token-classifies each row's status into delivered/in_transit/delayed/returned; counts + percentages | Unavailable without a status column; unclassifiable values counted separately, never guessed |
| 2 | **Delivery Time / On-Time Performance** (`_delivery_time_from_shipments`, line 416) | Overall on-time % (`actual ≤ expected`) plus average delivery days (`actual − ship_date`) | Unavailable without both delivery-date columns |
| 3 | **Shipping Cost Analysis** (`_cost_from_shipments`, line 495) | Total/average cost, per-carrier breakdown, and — if ≥2 monthly periods exist — period-over-period cost variance reusing the exact `variance`/`variance_pct` shape from Phase 30/31/33 | Unavailable without a cost column; cost trend simply omitted (not fabricated) below 2 periods |
| 4 | **Carrier/Route Performance Comparison** (`_carrier_route_performance`, line 591) | Constructed heuristic composite per carrier: `0.5×on_time_pct + 0.5×cost_component` (cost_component = 100 at the cheapest carrier's cost, scaled down proportionally for pricier carriers) when both available, else the single available component; route gets its own on-time%/avg-cost table (no composite score, per the brief's carrier-only scoping) | Explicitly `is_validated_instrument=False`, `confidence="constructed_heuristic_not_validated"` — same framing as Procurement's supplier score and Succession Readiness. Carriers with zero computable components are excluded, never force-scored |
| 5 | **Delay Analysis** (`_delay_analysis_from_shipments`, line 739) | Real lateness (`actual > expected`) broken down by carrier, route, and carrier×route; a combination is only labeled a delay "concentration" once it has ≥3 late shipments (`_MIN_LATE_FOR_CONCENTRATION_FLAG`) | Raw counts always shown even below the floor — just never editorialized as a "problem" until the sample is large enough |
| 6 | **Returns Analysis** (`_returns_from_shipments`, line 857) | Return rate from status/return-flag; if ≥5 return-reason texts exist, TF-IDF theme extraction against a fresh logistics-specific keyword dictionary, themes suppressed below 3 distinct shipments | Unavailable without a status/return-flag signal; theme analysis specifically degrades (return rate still shown) below the 5-reason floor |

---

## 3. On-Time-Performance Sharing Decision

**Shared, not duplicated.** The on-time arithmetic (group shipments by an entity name, compare
expected vs. actual date, compute a percentage) in Procurement's `_delivery_from_lines()` is
*exactly* the same computation Logistics needs — not merely similar. Rather than write it twice,
Phase 34:

1. Extracted the computation into a new, domain-agnostic module,
   `backend/core/delivery_performance_utils.py` (99 lines) — `compute_on_time_performance(rows)`
   takes `(group_key, expected_date, actual_date)` tuples and returns per-group on-time stats plus
   the list of groups with no complete date data.
2. Refactored `procurement_intelligence_engine.py`'s `_delivery_from_lines()` to call this shared
   utility internally, then map its generic output into Procurement's own unchanged
   `SupplierDeliveryItem`/`DeliveryPerformanceResult` dataclasses — Procurement's public API and
   field names are identical to before; only the internal computation now delegates. Verified with
   zero test changes needed: all 30 pre-existing Procurement tests still pass after the refactor.
3. `logistics_intelligence_engine.py` calls the same utility, grouped by carrier (item 4) and
   separately by route, mapping the output into its own `CarrierPerformanceItem`/
   `RoutePerformanceItem` dataclasses.

**What was deliberately NOT shared**: column detection, PO-line/shipment-record building, and
narrative text — these differ genuinely (Procurement's rows are purchase orders; Logistics' rows
are shipments) and sharing them would have forced an artificial coupling between two otherwise
independent domains.

---

## 4. Returns-Theme-Extraction Reuse Decision

Also genuine reuse, not duplication, but narrower than a whole-function reuse:

- **Promoted to public, reused directly**: `exit_interview_intelligence_engine.py`'s
  `scrub_pii()`, `extract_top_terms_tfidf()` / `extract_top_terms_word_frequency()`,
  `SKLEARN_AVAILABLE`, `MIN_DOCUMENT_FREQUENCY` (3), and `MIN_RESPONSES_FOR_AGGREGATE` (5) were
  renamed from `_`-prefixed (module-private) to public names this phase specifically so
  `logistics_intelligence_engine.py` could import and call them — see that module's updated
  docstring. Verified with the full exit-interview (19) and recruitment-pipeline (24) test suites
  passing unchanged after the rename.
- **Deliberately NOT reused**: `THEME_KEYWORDS` and `_classify_response()` — these encode HR
  attrition constructs (JD-R, COR, Equity, Mobley, FFM) with zero semantic overlap with logistics
  return reasons ("damaged in transit", "wrong item"). This is a different call from
  `recruitment_pipeline_engine.py`'s existing precedent, which reuses
  `analyze_exit_interview_text()` *wholesale* for rejection-reason themes — a defensible choice
  there since candidate-rejection language plausibly overlaps with the same HR constructs. Logistics
  return reasons don't, so reusing the whole function would have silently produced an empty/wrong
  result (no HR phrase ever matches a shipping complaint). A fresh, logistics-specific theme
  dictionary (`_RETURN_THEME_KEYWORDS`, line ~692) was built instead, while genuinely sharing the
  extraction mechanism and privacy discipline.

---

## 5. Fixture Design

`logistics_shipments_test_data.csv` (repo root, 60 shipments, 4 carriers, 4 routes, 2025-11 to
2026-04) — built via a scratch script, cross-verified with pandas before any test was written:

- **Carrier differentiation (item 4)**: DHL Saudi (92.3% on-time, premium SAR 67.50 avg — best
  delivery, worst cost), SMSA Express (86.7%, SAR 44.81), Aramex (71.4%, cheapest at SAR 35.75),
  Fetchr Logistics (58.3%, SAR 40.50 — worst delivery) — a genuine trade-off surface, not a
  monotonic "best at everything" carrier.
- **Delay concentration (item 5)**: Fetchr Logistics × Riyadh-Dammam has 5 late shipments (avg 6.0
  days late) — clears the 3-shipment floor and is flagged. Aramex × Dammam-Khobar (4 late) also
  clears it. SMSA × Riyadh-Jeddah (2 late) and DHL × Jeddah-Makkah (1 late) stay below the floor
  and are correctly NOT flagged, even though their raw counts are still shown.
- **Returns with theme diversity (item 6)**: 11 returned shipments with reason text. Three themes
  (Damaged in Transit, Wrong Item Shipped, Defective Product) land at exactly 3 mentions each —
  the minimum to clear the suppression floor. A fourth theme (Late Delivery) deliberately has only
  2 mentions — below the floor, proving suppression actually triggers, not just theoretically
  exists.
- **In-transit/delayed rows with incomplete dates**: 4 in-transit and 2 delayed shipments have an
  expected date but no actual delivery date yet (still in flight) — correctly excluded from the
  on-time/delay calculations (54 of 60 shipments have complete date pairs), not defaulted to
  either on-time or late.
- **Returns decoupled from delivery lateness**: return shipments were deliberately given
  actual-delivery-date == expected-delivery-date (delivered on time, then returned for an
  unrelated reason) — this was a real fix made during fixture construction after the first draft
  accidentally made every return "late by construction," contaminating the delay-concentration
  numbers. Documented here as a real design correction, not hidden.

---

## 6. Test Results

**New tests**: `tests/test_logistics_intelligence_engine.py` — 29/29 passing, organized into 8
sections covering all 6 items' hand-computed figures, cross-module honest degradation, and
bundle/serialization sanity. One test (`test_unavailable_on_procurement_fixture`) specifically
proves the per-row shipment-building guard excludes every row of Procurement's fixture even though
its delivery-date columns superficially match Logistics' patterns — confirmed live (§7).

**Full regression suite**: `1753 passed, 1 skipped, 1 failed` (the same pre-existing, unrelated
`test_health_wheel_imported` failure present before this phase — 1724 baseline + 29 new tests =
1753). **Zero regressions**, including in the refactored Procurement module and the renamed Exit
Interview utilities.

---

## 7. Live Browser Verification

Playwright run against the live backend + Vite dev server. Zero console/page errors
(`CONSOLE_ERRORS: []`).

| Screenshot | Confirmed |
|---|---|
| Status Overview tab | 60 total; 43 delivered/11 returned/4 in-transit/2 delayed — exact match |
| Delivery Time tab | 77.8% on-time (42/54), 4.1 avg delivery days — exact match |
| Shipping Cost tab | SAR 2,801.00 total; per-carrier totals (DHL 945.00, SMSA 717.00, Aramex 572.00, Fetchr 567.00); 5-row monthly trend table — exact match |
| Carrier & Route tab | Prominent "CONSTRUCTED HEURISTIC... NOT a validated... rating" disclaimer; all 4 composite scores (Aramex 85.7, SMSA 80.7, Fetchr 72.5, DHL 51.7) and 4-route breakdown — exact match |
| Delay Analysis tab | 12 late total; Fetchr·Riyadh-Dammam and Aramex·Dammam-Khobar flagged "Concentration"; SMSA·Riyadh-Jeddah and DHL·Jeddah-Makkah correctly show no flag — exact match |
| Returns tab | 18.33% return rate; 3 themes at exactly 3 shipments/27.3% each; "Late Delivery" correctly absent (suppressed); TF-IDF top terms shown, no raw reason text anywhere — exact match |
| Cross-module: uploading Procurement's fixture, Returns tab | "Returns analysis not available... no row had a usable shipment record" — Expected/Actual delivery date correctly shown as detected (green, since Procurement's PO dates structurally match), but Carrier/Status/Cost/ReturnFlag correctly shown as missing, so nothing is computed |

**A UI polish bug found and fixed during this verification**: the frontend's column-label maps
were initially missing entries for `return_flag` and `delay_reason` (present in the backend's
`columns_detected` payload but not in the two `COLUMN_LABELS_EN/AR` dictionaries), so those two
checklist rows briefly rendered as raw snake_case instead of a readable label. Fixed by adding the
missing entries; re-verified live that both now render correctly (screenshot re-captured post-fix).

---

## 8. Phase 2 Backlog

- **Delay forecasting/prediction** — explicitly deferred, as specified.
- **Supply-chain risk scoring beyond the carrier performance composite** — explicitly deferred, as
  specified. True multi-tier supply-chain risk needs data this platform doesn't have (financial
  health of carriers, geopolitical/weather risk feeds, etc.).
- **Route optimization** — explicitly deferred, as specified, and flagged here as a genuinely
  **different kind of feature** from everything built across all five Business Intelligence
  modules so far. Every item built in Phases 30–34 is a reporting/analytics feature: it describes
  what already happened in the uploaded data (spend, trends, performance, delays, returns).
  Route optimization is a combinatorial/operations-research problem (e.g., vehicle routing,
  network-flow minimization) — it would compute a *new* recommended plan, not describe historical
  data. It requires a different algorithmic toolkit entirely and should not be assumed to be "more
  reporting to build later" — it's a different product capability.
- **Delay-reason/cause breakdown** — the brief asked for delay analysis "by carrier/route/cause-
  if-available." A `delay_reason` column is fuzzy-detected (`columns_detected["delay_reason"]`)
  but this phase's fixture has no such column (delayed shipments have no cause data, only returned
  shipments have reason text, and reusing return-reasons for delay-cause would conflate two
  different real-world events). Cause-breakdown is implemented to activate automatically the
  moment a real delay-cause column is present in an upload — it was not stubbed or faked here.

---

## Regression Count

**1753 passed, 1 skipped, 1 pre-existing unrelated failure. Zero regressions.**

## Environment Note

Same dev-environment ghost-socket condition as Phases 30-33; `executive-ui/vite.config.ts`'s
proxy target (pointed at the LAN IP since Phase 31) was reused unchanged.
